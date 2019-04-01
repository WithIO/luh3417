from dataclasses import dataclass, replace
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Dict, List, Optional, Sequence, Text, Union

from libcloud.dns.base import DNSDriver, Record
from libcloud.dns.base import Zone as CloudZone
from libcloud.dns.providers import get_driver
from libcloud.dns.types import RecordType

IpAddress = Union[IPv4Address, IPv6Address, Text]


class RecordSetError(Exception):
    pass


def parse_domain(domain: Union[Text, "Domain"]) -> "Domain":
    """
    Transforms a domain as a text string into a Domain instance. Calling with
    a domain will return a copy of the said domain
    """

    if isinstance(domain, Domain):
        return replace(domain)
    else:
        parts = tuple(p.lower() for p in reversed(domain.split(".")))

        if any(not p for p in parts):
            raise RecordSetError(f"Domain {domain} does not appear to be valid")

        return Domain(domain, tuple(p.lower() for p in reversed(domain.split("."))))


@dataclass
class Domain:
    """
    Lightly-parsed domain name, mostly here to do some basic operations (see
    below)
    """

    domain: Text
    parts: Sequence[Text]

    def __str__(self):
        """
        Transforms back the domain into a string
        """

        return self.domain

    def __eq__(self, other: Union[Text, "Domain"]):
        """
        Tests the equality domain-wise (aka case-insensitive)
        """

        other = parse_domain(other)
        return self.parts == other.parts

    def contains(self, other: Union[Text, "Domain"]) -> bool:
        """
        Tests of the other domain is a sub-domain or equal to the current
        domain
        """

        other = parse_domain(other)

        try:
            for i, part in enumerate(self.parts):
                if other.parts[i] != part:
                    return False
        except IndexError:
            return False
        else:
            return True

    def truncate(self, other: Union[Text, "Domain"]) -> "Domain":
        """
        Returns the other domain without the current domain. By example:

        >>> d = parse_domain('foo.com')
        >>> assert d.truncate('bar.foo.com') == 'bar'
        """

        other = parse_domain(other)

        if not self.contains(other):
            raise RecordSetError(
                f"Cannot truncate {other} with {self} because not contained"
            )

        i = 0

        try:
            for i, part in enumerate(self.parts):
                if other.parts[i] != part:
                    break
        except IndexError:
            pass

        out = other.parts[i + 1 :]

        return Domain(domain=".".join(reversed(out)), parts=tuple(out))


def list_or_iterate(obj, word, *args, **kwargs):
    """
    Tries both the iterate and the list methods from libcloud (wtf aren't both
    implemented?)
    """

    try:
        return getattr(obj, f"iterate_{word}")(*args, **kwargs)
    except NotImplementedError:
        return getattr(obj, f"list_{word}")(*args, **kwargs)


@dataclass
class Zone:
    """
    A DNS zone, represented by its domain (like my.org), a provider (like
    digitalocean) and credentials which is a kwarg dict which will be passed
    to the constructor of the provider.
    """

    domain: Domain
    provider: Text
    credentials: Dict[Text, Text]

    def get_cloud_zone(self, driver: DNSDriver) -> Optional[CloudZone]:
        """
        Go get the equivalent libcloud zone from the driver
        """

        for zone in list_or_iterate(driver, "zones"):
            if self.domain == zone.domain:
                return zone


class RecordSet:
    """
    A class to manage records by set instead of creating them alone
    """

    def __init__(self, zones: Sequence[Zone]):
        self.zones = zones

    def _get_zone_info(self, domain):
        """
        Computes and checks some zone info
        """

        zone = self.get_zone(domain)

        if not zone:
            raise RecordSetError(f"Cannot find a zone for {domain}")

        driver = self.get_driver(zone)
        cloud_zone = zone.get_cloud_zone(driver)

        if not cloud_zone:
            raise RecordSetError(f"Cannot find the zone for {domain} in the provider")

        sub_domain = zone.domain.truncate(domain)

        return cloud_zone, driver, sub_domain

    def get_zone(self, domain: Union[Domain, Text]) -> Optional[Zone]:
        """
        Given a domain, returns the first matching zone (aka zone which
        contains the provided domain)
        """

        domain = parse_domain(domain)

        for zone in self.zones:
            if zone.domain.contains(domain):
                return zone

    def get_driver(self, zone: Zone) -> DNSDriver:
        """
        Given a zone, starts the appropriate driver
        """

        cls = get_driver(zone.provider)
        return cls(**zone.credentials)

    def set_ips(self, domain: Union[Domain, Text], ips: Sequence[IpAddress]):
        """
        Given a domain and a set of IP addresses, defines the correct A and
        AAAA records while also deleting the extraneous one (and CNAME too)
        """

        cloud_zone, driver, sub_domain = self._get_zone_info(domain)

        expected_ips = set(ip_address(ip) for ip in ips)
        found_ips = set()
        to_delete: List[Record] = []

        for record in list_or_iterate(driver, "records", cloud_zone):  # type: Record
            if sub_domain == record.name:
                if record.type in {RecordType.A, RecordType.AAAA}:
                    ip = ip_address(record.data)
                    found_ips.add(ip)

                    if ip not in expected_ips:
                        to_delete.append(record)
                elif record.type == RecordType.CNAME:
                    to_delete.append(record)

        for record in to_delete:
            record.delete()

        for ip in expected_ips - found_ips:
            driver.create_record(
                name=f"{sub_domain}",
                zone=cloud_zone,
                type=RecordType.A if ip.version == 4 else RecordType.AAAA,
                data=f"{ip}",
            )

    def set_alias(self, domain: Union[Domain, Text], target: Union[Text, Domain]):
        """
        Sets the domain to be an alias. It will first remove any AAAA or A
        record attached to this domain.
        """

        cloud_zone, driver, sub_domain = self._get_zone_info(domain)
        target = parse_domain(target)
        to_delete: List[Record] = []
        to_check: Optional[Record] = None

        for record in list_or_iterate(driver, "records", cloud_zone):  # type: Record
            if sub_domain == record.name:
                if record.type in {RecordType.A, RecordType.AAAA}:
                    to_delete.append(record)
                elif record.type == RecordType.CNAME:
                    to_check = record

        for record in to_delete:
            record.delete()

        if to_check:
            if target != to_check.data:
                to_check.update(data=f"{target}.")
        else:
            driver.create_record(
                name=f"{sub_domain}",
                data=f"{target}.",
                type=RecordType.CNAME,
                zone=cloud_zone,
            )
