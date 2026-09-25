# PostgreSQL repositories and Unit of Work (STO-08)

`UnitOfWork` owns exactly one SQLAlchemy session and exposes repositories for all current
aggregate tables. A successful service explicitly calls `commit()`; exceptions cause rollback and
the session is always closed.

Repositories return model objects without exposing SQLAlchemy queries to services. Camera and Case
queries accept `ActorContext` for area/owner scoping. List operations use ordered UUID cursor
pagination with a maximum page size of 100. Case updates can include the previously observed
`updated_at` value; a zero-row conditional update raises `ConcurrentUpdateError`.

Unique, foreign-key and check violations are mapped to domain-facing persistence errors. Services
therefore do not depend on driver error codes or SQLAlchemy exception classes.
