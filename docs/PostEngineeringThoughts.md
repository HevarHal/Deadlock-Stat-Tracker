# Deadlock Stat Tracker — Post-Engineering Thoughts

## Overview

I built Deadlock Stat Tracker to search Steam players and present their Deadlock statistics, match history, ranks, item timelines, and starting build guides. The project became a useful exercise in building and deploying a complete application rather than stopping at a local prototype.

## Architecture

The application is a modular monolith deployed on one AWS EC2 instance with Docker Compose. Caddy handles HTTPS and forwards requests to an Nginx container, which serves the Vite-built JavaScript frontend and proxies `/api` requests to FastAPI. The backend retrieves data from the public Deadlock API and uses PostgreSQL for cached seasonal summaries.

This was an appropriate design for the project's size. Separating it into microservices would have increased deployment and debugging complexity without providing a practical benefit.

The original architecture included PostgreSQL even though it stored only seasonal summaries derived from upstream data. Those summaries become stale within minutes and must be fetched again, so retaining them across restarts provides little value. I could have started with FastAPI and a bounded in-memory cache, then added Docker when repeatable deployment became useful. Docker still simplified packaging the finished application, but neither Docker nor PostgreSQL was required to implement temporary caching.

## Caching problems

The first implementation repeated expensive upstream work. The summary and match-history endpoints could download and decode the same player history independently, HTTP clients were not shared for the application's lifetime, and asset data was fetched more often than necessary. Pandas was also being used for relatively small aggregations that could be calculated in one Python pass.

I replaced that behavior with one reusable asynchronous HTTP client and a bounded, worker-local cache. Simultaneous requests for the same resource now share one in-flight request. Successful match data is cached for five minutes, catalogs for one hour, and failed or malformed responses are not retained. The cache is limited to 128 entries and 32 MiB of serialized response data. Seasonal summaries stored in PostgreSQL retain the original upstream fetch time so writing a summary does not incorrectly extend its freshness.

The more important tradeoff for the current deployment is memory usage. Cached responses can be large, and parsed Python objects consume more memory than their serialized response bodies. Entry and byte limits are therefore necessary so the cache cannot grow without bound. Losing this cache during a restart is acceptable because the data can be fetched again.

## Performance results

I measured five rounds on the EC2 host before and after the caching changes and verified that the final response bodies were identical. Median response times changed as follows:

| Workload | Before | After | Improvement |
| --- | ---: | ---: | ---: |
| All-time profile | 234.20 ms | 5.09 ms | 46.0× |
| Match-history page two | 151.76 ms | 2.33 ms | 65.1× |
| Season 1 profile | 226.02 ms | 5.98 ms | 37.8× |
| Expanded match build | 253.35 ms | 2.15 ms | 117.8× |

These results mostly represent cache hits, not general request capacity. Cold requests still depend on the latency and availability of the Deadlock API, and the benchmark did not include the visitor's network connection, TLS, browser rendering, or concurrent-user load.

## What I would change next time

For a future project, I would define typed API response models and validate external API data at the boundary from the beginning. I would also decide early whether any data genuinely needs to survive a restart. I would begin with a bounded in-memory cache for replaceable upstream data and add a database only for durable application state. If a relational database were required, I would use Alembic migrations instead of modifying its schema during application startup.

I would establish a shared HTTP client, timeout policy, dependency locking, and continuous-integration checks before adding many features. I would also add a real PostgreSQL integration test, a small browser end-to-end suite, and readiness checks that verify actual dependencies rather than only confirming that the web process responds.

The largest lesson was understanding when data should be persistent. A database backed by a Docker volume is valuable when application data must survive container restarts and remains useful over time. It added little value for summaries derived from an external API because repeated API calls make that data stale within minutes. For short-lived, replaceable data, a bounded in-memory cache is simpler; persistent storage should be reserved for information the application cannot cheaply recreate.
