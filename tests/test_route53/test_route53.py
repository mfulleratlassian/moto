from __future__ import unicode_literals

import boto
from boto.route53.healthcheck import HealthCheck
from boto.route53.record import ResourceRecordSets

import sure  # noqa

from moto import mock_route53


@mock_route53
def test_hosted_zone():
    conn = boto.connect_route53('the_key', 'the_secret')
    firstzone = conn.create_hosted_zone("testdns.aws.com")
    zones = conn.get_all_hosted_zones()
    len(zones["ListHostedZonesResponse"]["HostedZones"]).should.equal(1)

    conn.create_hosted_zone("testdns1.aws.com")
    zones = conn.get_all_hosted_zones()
    len(zones["ListHostedZonesResponse"]["HostedZones"]).should.equal(2)

    id1 = firstzone["CreateHostedZoneResponse"]["HostedZone"]["Id"].split("/")[-1]
    zone = conn.get_hosted_zone(id1)
    zone["GetHostedZoneResponse"]["HostedZone"]["Name"].should.equal("testdns.aws.com")

    conn.delete_hosted_zone(id1)
    zones = conn.get_all_hosted_zones()
    len(zones["ListHostedZonesResponse"]["HostedZones"]).should.equal(1)

    conn.get_hosted_zone.when.called_with("abcd").should.throw(boto.route53.exception.DNSServerError, "404 Not Found")


@mock_route53
def test_rrset():
    conn = boto.connect_route53('the_key', 'the_secret')

    conn.get_all_rrsets.when.called_with("abcd", type="A").should.throw(
        boto.route53.exception.DNSServerError, "404 Not Found")

    zone = conn.create_hosted_zone("testdns.aws.com")
    zoneid = zone["CreateHostedZoneResponse"]["HostedZone"]["Id"].split("/")[-1]

    changes = ResourceRecordSets(conn, zoneid)
    change = changes.add_change("CREATE", "foo.bar.testdns.aws.com", "A")
    change.add_value("1.2.3.4")
    changes.commit()

    rrsets = conn.get_all_rrsets(zoneid, type="A")
    rrsets.should.have.length_of(1)
    rrsets[0].resource_records[0].should.equal('1.2.3.4')

    rrsets = conn.get_all_rrsets(zoneid, type="CNAME")
    rrsets.should.have.length_of(0)

    changes = ResourceRecordSets(conn, zoneid)
    changes.add_change("DELETE", "foo.bar.testdns.aws.com", "A")
    change = changes.add_change("CREATE", "foo.bar.testdns.aws.com", "A")
    change.add_value("5.6.7.8")
    changes.commit()

    rrsets = conn.get_all_rrsets(zoneid, type="A")
    rrsets.should.have.length_of(1)
    rrsets[0].resource_records[0].should.equal('5.6.7.8')

    changes = ResourceRecordSets(conn, zoneid)
    changes.add_change("DELETE", "foo.bar.testdns.aws.com", "A")
    changes.commit()

    rrsets = conn.get_all_rrsets(zoneid)
    rrsets.should.have.length_of(0)

    changes = ResourceRecordSets(conn, zoneid)
    change = changes.add_change("CREATE", "foo.bar.testdns.aws.com", "A")
    change.add_value("1.2.3.4")
    change = changes.add_change("CREATE", "bar.foo.testdns.aws.com", "A")
    change.add_value("5.6.7.8")
    changes.commit()

    rrsets = conn.get_all_rrsets(zoneid, type="A")
    rrsets.should.have.length_of(2)

    rrsets = conn.get_all_rrsets(zoneid, name="foo.bar.testdns.aws.com", type="A")
    rrsets.should.have.length_of(1)
    rrsets[0].resource_records[0].should.equal('1.2.3.4')

    rrsets = conn.get_all_rrsets(zoneid, name="bar.foo.testdns.aws.com", type="A")
    rrsets.should.have.length_of(1)
    rrsets[0].resource_records[0].should.equal('5.6.7.8')

    rrsets = conn.get_all_rrsets(zoneid, name="foo.foo.testdns.aws.com", type="A")
    rrsets.should.have.length_of(0)


@mock_route53
def test_create_health_check():
    conn = boto.connect_route53('the_key', 'the_secret')

    check = HealthCheck(
        ip_addr="10.0.0.25",
        port=80,
        hc_type="HTTP",
        resource_path="/",
        fqdn="example.com",
        string_match="a good response",
        request_interval=10,
        failure_threshold=2,
    )
    conn.create_health_check(check)

    checks = conn.get_list_health_checks()['ListHealthChecksResponse']['HealthChecks']
    list(checks).should.have.length_of(1)
    check = checks[0]
    config = check['HealthCheckConfig']
    config['IPAddress'].should.equal("10.0.0.25")
    config['Port'].should.equal("80")
    config['Type'].should.equal("HTTP")
    config['ResourcePath'].should.equal("/")
    config['FullyQualifiedDomainName'].should.equal("example.com")
    config['SearchString'].should.equal("a good response")
    config['RequestInterval'].should.equal("10")
    config['FailureThreshold'].should.equal("2")


@mock_route53
def test_delete_health_check():
    conn = boto.connect_route53('the_key', 'the_secret')

    check = HealthCheck(
        ip_addr="10.0.0.25",
        port=80,
        hc_type="HTTP",
        resource_path="/",
    )
    conn.create_health_check(check)

    checks = conn.get_list_health_checks()['ListHealthChecksResponse']['HealthChecks']
    list(checks).should.have.length_of(1)
    health_check_id = checks[0]['Id']

    conn.delete_health_check(health_check_id)
    checks = conn.get_list_health_checks()['ListHealthChecksResponse']['HealthChecks']
    list(checks).should.have.length_of(0)


@mock_route53
def test_use_health_check_in_resource_record_set():
    conn = boto.connect_route53('the_key', 'the_secret')

    check = HealthCheck(
        ip_addr="10.0.0.25",
        port=80,
        hc_type="HTTP",
        resource_path="/",
    )
    check = conn.create_health_check(check)['CreateHealthCheckResponse']['HealthCheck']
    check_id = check['Id']

    zone = conn.create_hosted_zone("testdns.aws.com")
    zone_id = zone["CreateHostedZoneResponse"]["HostedZone"]["Id"].split("/")[-1]

    changes = ResourceRecordSets(conn, zone_id)
    change = changes.add_change("CREATE", "foo.bar.testdns.aws.com", "A", health_check=check_id)
    change.add_value("1.2.3.4")
    changes.commit()

    record_sets = conn.get_all_rrsets(zone_id)
    record_sets[0].health_check.should.equal(check_id)
