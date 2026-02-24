# syntax=docker/dockerfile:1.7

ARG TRINO_VERSION=455

FROM maven:3.9.9-eclipse-temurin-23 AS builder
ARG TRINO_VERSION

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${TRINO_VERSION}" https://github.com/trinodb/trino.git /build/trino

COPY langbridge/services/trino/custom/patches /patches

WORKDIR /build/trino

RUN git apply /patches/0001-tenant-aware-jdbc-routing.patch

RUN ./mvnw -B \
    -DskipTests \
    -Dair.check.skip-all \
    -pl :trino-base-jdbc,:trino-postgresql,:trino-mysql,:trino-sqlserver \
    -am package

FROM trinodb/trino:${TRINO_VERSION}
ARG TRINO_VERSION

USER root

COPY --from=builder /build/trino/plugin/trino-base-jdbc/target/trino-base-jdbc-*.jar /tmp/trino-patch/
COPY --from=builder /build/trino/plugin/trino-postgresql/target/trino-postgresql-*.jar /tmp/trino-patch/
COPY --from=builder /build/trino/plugin/trino-mysql/target/trino-mysql-*.jar /tmp/trino-patch/
COPY --from=builder /build/trino/plugin/trino-sqlserver/target/trino-sqlserver-*.jar /tmp/trino-patch/

RUN set -eux; \
    rm -f /usr/lib/trino/plugin/postgresql/trino-postgresql-*.jar; \
    rm -f /usr/lib/trino/plugin/mysql/trino-mysql-*.jar; \
    rm -f /usr/lib/trino/plugin/sqlserver/trino-sqlserver-*.jar; \
    cp /tmp/trino-patch/trino-postgresql-*.jar /usr/lib/trino/plugin/postgresql/; \
    cp /tmp/trino-patch/trino-mysql-*.jar /usr/lib/trino/plugin/mysql/; \
    cp /tmp/trino-patch/trino-sqlserver-*.jar /usr/lib/trino/plugin/sqlserver/; \
    for plugin in postgresql mysql sqlserver; do \
      rm -f "/usr/lib/trino/plugin/${plugin}/trino-base-jdbc-"*.jar; \
      cp /tmp/trino-patch/trino-base-jdbc-*.jar "/usr/lib/trino/plugin/${plugin}/"; \
    done; \
    rm -rf /tmp/trino-patch

USER trino
