package io.trino.plugin.jdbc;

import io.opentelemetry.api.OpenTelemetry;
import io.trino.plugin.jdbc.credential.CredentialPropertiesProvider;
import io.trino.plugin.jdbc.credential.CredentialProvider;
import io.trino.plugin.jdbc.credential.DefaultCredentialPropertiesProvider;
import io.trino.spi.connector.ConnectorSession;
import io.trino.spi.security.ConnectorIdentity;

import java.sql.Connection;
import java.sql.Driver;
import java.sql.SQLException;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Properties;
import java.util.regex.Pattern;

import static com.google.common.base.Preconditions.checkState;

/**
 * ConnectionFactory that materializes tenant-aware JDBC URL templates.
 *
 * <p>The URL template must contain "{tenant}" and may contain "{source}".
 * Values are read from Trino extra credentials.
 */
public final class TenantAwareConnectionFactory
        implements ConnectionFactory
{
    private static final String TENANT_PLACEHOLDER = "{tenant}";
    private static final String SOURCE_PLACEHOLDER = "{source}";
    private static final Pattern SAFE_TOKEN = Pattern.compile("^[A-Za-z0-9_.:-]+$");

    private final Driver driver;
    private final String connectionUrlTemplate;
    private final Properties connectionProperties;
    private final CredentialPropertiesProvider<String, String> credentialPropertiesProvider;
    private final OpenTelemetry openTelemetry;
    private final String tenantCredentialKey;
    private final String sourceCredentialKey;

    public TenantAwareConnectionFactory(
            Driver driver,
            String connectionUrlTemplate,
            CredentialProvider credentialProvider,
            Properties baseConnectionProperties,
            OpenTelemetry openTelemetry)
    {
        this(
                driver,
                connectionUrlTemplate,
                new DefaultCredentialPropertiesProvider(Objects.requireNonNull(credentialProvider, "credentialProvider is null")),
                baseConnectionProperties,
                openTelemetry,
                "tenant",
                "source");
    }

    public TenantAwareConnectionFactory(
            Driver driver,
            String connectionUrlTemplate,
            CredentialPropertiesProvider<String, String> credentialPropertiesProvider,
            Properties baseConnectionProperties,
            OpenTelemetry openTelemetry,
            String tenantCredentialKey,
            String sourceCredentialKey)
    {
        this.driver = Objects.requireNonNull(driver, "driver is null");
        this.connectionUrlTemplate = Objects.requireNonNull(connectionUrlTemplate, "connectionUrlTemplate is null");
        this.connectionProperties = new Properties();
        this.connectionProperties.putAll(Objects.requireNonNull(baseConnectionProperties, "baseConnectionProperties is null"));
        this.credentialPropertiesProvider = Objects.requireNonNull(credentialPropertiesProvider, "credentialPropertiesProvider is null");
        this.openTelemetry = Objects.requireNonNull(openTelemetry, "openTelemetry is null");
        this.tenantCredentialKey = Objects.requireNonNull(tenantCredentialKey, "tenantCredentialKey is null");
        this.sourceCredentialKey = Objects.requireNonNull(sourceCredentialKey, "sourceCredentialKey is null");
    }

    @Override
    public Connection openConnection(ConnectorSession session)
            throws SQLException
    {
        Map<String, String> extraCredentials = readExtraCredentials(session);
        String tenantId = getRequiredCredential(extraCredentials, tenantCredentialKey);
        String sourceId = getOptionalCredential(extraCredentials, sourceCredentialKey);
        String resolvedUrl = materializeConnectionUrl(connectionUrlTemplate, tenantId, sourceId);

        Properties properties = getConnectionProperties(session.getIdentity());
        materializePropertyTemplates(properties, tenantId, sourceId);
        TracingDataSource dataSource = new TracingDataSource(openTelemetry, driver, resolvedUrl);
        Connection connection = dataSource.getConnection(properties);
        checkState(connection != null, "Driver returned null connection for URL '%s' and driver %s", resolvedUrl, driver);
        return connection;
    }

    private Properties getConnectionProperties(ConnectorIdentity identity)
    {
        Properties properties = new Properties();
        properties.putAll(connectionProperties);
        properties.putAll(credentialPropertiesProvider.getCredentialProperties(identity));
        return properties;
    }

    static String materializeConnectionUrl(String template, String tenantId, String sourceId)
            throws SQLException
    {
        String resolved = template.replace(TENANT_PLACEHOLDER, sanitize("tenant", tenantId));

        if (resolved.contains(SOURCE_PLACEHOLDER)) {
            if (sourceId == null || sourceId.isBlank()) {
                throw new SQLException("Connection URL requires source credential but it is missing");
            }
            resolved = resolved.replace(SOURCE_PLACEHOLDER, sanitize("source", sourceId));
        }

        return resolved;
    }

    static void materializePropertyTemplates(Properties properties, String tenantId, String sourceId)
            throws SQLException
    {
        String sanitizedTenant = sanitize("tenant", tenantId);
        String sanitizedSource = null;
        if (sourceId != null && !sourceId.isBlank()) {
            sanitizedSource = sanitize("source", sourceId);
        }

        for (String key : properties.stringPropertyNames()) {
            String value = properties.getProperty(key);
            if (value == null) {
                continue;
            }

            String resolved = value.replace(TENANT_PLACEHOLDER, sanitizedTenant);
            if (resolved.contains(SOURCE_PLACEHOLDER)) {
                if (sanitizedSource == null) {
                    throw new SQLException("Connection property '" + key + "' requires source credential but it is missing");
                }
                resolved = resolved.replace(SOURCE_PLACEHOLDER, sanitizedSource);
            }
            properties.setProperty(key, resolved);
        }
    }

    static Map<String, String> readExtraCredentials(ConnectorSession session)
            throws SQLException
    {
        if (session == null) {
            throw new SQLException("Connector session is required");
        }
        ConnectorIdentity identity = session.getIdentity();
        if (identity == null) {
            throw new SQLException("Connector identity is required");
        }
        return identity.getExtraCredentials();
    }

    static String getRequiredCredential(Map<String, String> credentials, String key)
            throws SQLException
    {
        Optional<String> value = Optional.ofNullable(credentials.get(key))
                .map(String::trim)
                .filter(v -> !v.isBlank());
        if (value.isEmpty()) {
            throw new SQLException("Missing required Trino extra credential: " + key);
        }
        return value.get();
    }

    static String getOptionalCredential(Map<String, String> credentials, String key)
    {
        return Optional.ofNullable(credentials.get(key))
                .map(String::trim)
                .filter(v -> !v.isBlank())
                .orElse(null);
    }

    static String sanitize(String label, String value)
            throws SQLException
    {
        if (!SAFE_TOKEN.matcher(value).matches()) {
            throw new SQLException("Invalid " + label + " value for JDBC routing token");
        }
        return value;
    }
}
