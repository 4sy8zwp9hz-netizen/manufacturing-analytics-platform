# Deployment Evolution

This document describes how the engineering application evolved into a centrally hosted production
service.

## Progression

```text
personal engineering analysis
        ↓
local interactive application
        ↓
packaged desktop release
        ↓
versioned/shared application distribution
        ↓
central Windows server
        ↓
Flask application portal + mounted Dash apps
        ↓
Waitress-hosted browser access
        ↓
scheduled refresh, health checks, logs, restart support
```

## Relationship to the Yield backend

Application distribution and Yield data processing improved together, but they solved different
problems:

- the distribution track standardized how applications were packaged, discovered, mounted,
  hosted, checked, restarted, and supported;
- the Yield backend track standardized how manufacturing data was retrieved, transformed,
  materialized, refreshed, validated, and served to the interface.

Central hosting increased the importance of shared state, bounded resources, and predictable
background work. In the other direction, prepared data and workload-specific refresh behavior made
it practical for one hosted service to support multiple browser users without repeating the same
source work for every session. Neither track replaces the other.

## Why each step happened

### Local application

The initial goal was to make repeated engineering investigation possible. A local Dash server and,
where useful, a desktop webview made the Python application accessible without requiring users to
work directly in Python.

### Packaging and shared releases

Adoption introduced versioning, dependency, update, and configuration problems. Packaged releases,
stable filenames, manifests/version pointers, local installation behavior, shared configuration,
and documentation were responses to those operational needs.

### Central application access

Maintaining multiple installed copies and repeating data work per user became inefficient. A common
application portal provided one browser entry point and mounted several Dash WSGI applications
beneath a Flask shell. Waitress served the combined application on the internal Windows host.

### Persistent operation

Server-hosted software required behavior beyond “run the Python file”:

- stable launch scripts suitable for scheduled execution;
- log separation and unbuffered runtime output;
- a health endpoint;
- watchdog/restart behavior after outages;
- background services that do not depend on an open browser;
- safe failure states for independently mounted applications;
- explicit route prefixes and preservation of query strings.

## Sanitized infrastructure case study

Operationalizing the applications required working through enterprise constraints including:

- appropriate Windows server hardware and runtime environment;
- corporate-domain integration;
- stable internal addressing;
- firewall and security-policy restrictions;
- SQL Server permissions and driver availability;
- shared-resource permissions;
- internal TCP access;
- persistent execution after restart or outage.

No private hostname, IP address, domain, port assignment, network path, credential, or ticket detail
is included here.

## Role boundary

The accurate statement is:

> Worked with IT to resolve domain, firewall, stable-addressing, SQL-access, and persistent-hosting
> requirements necessary to deploy internally developed manufacturing applications.

This does not claim personal administration of the enterprise network. Likewise, where an MES or
database team implemented upstream source changes, the role was to define, request, validate, and
integrate the application data requirements.

## Public implementation

The public project runs as one Waitress-hosted Dash application. Its application factory accepts a
base path compatible with mounting in a larger Flask portal, but the public repository does not
fabricate all related internal applications into one demo.
