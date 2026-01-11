# Security & Threat Model

## Threat Model

### Identified Threats

1. **Prompt Injection**
   - **Risk**: Malicious content in retrieved sources could manipulate LLM behavior
   - **Mitigation**: Pattern-based detection, context sanitization, system prompt instructions

2. **Rate Limiting Abuse**
   - **Risk**: DoS attacks or API abuse
   - **Mitigation**: In-memory rate limiting (100 req/min per IP), upgrade to Redis in production

3. **Data Leakage**
   - **Risk**: Sensitive data in logs or responses
   - **Mitigation**: No PII logging, secret management via env vars, response sanitization

4. **SQL Injection**
   - **Risk**: Malicious input in database queries
   - **Mitigation**: SQLModel/ORM prevents raw SQL, parameterized queries

5. **Vector Database Injection**
   - **Risk**: Malicious payloads in Qdrant
   - **Mitigation**: Input validation, payload sanitization

## Security Controls

### Prompt Injection Defense

- Pattern matching for common injection patterns
- Context sanitization (truncation, whitespace normalization)
- System prompt explicitly instructs to ignore source instructions
- Suspicious context flagging

### Rate Limiting

- Simple in-memory store (per-IP)
- 100 requests per minute default
- 429 response with Retry-After header
- **Production**: Use Redis for distributed rate limiting

### Secret Management

- All secrets via environment variables
- `.env` file in `.gitignore`
- No hardcoded credentials
- Support for AWS Secrets Manager (future)

### CORS

- Configured for specific frontend origins
- Credentials allowed for authenticated requests
- No wildcard origins

### Input Validation

- Pydantic models for all API inputs
- Type checking and validation
- Request size limits (implicit via FastAPI)

## Privacy Considerations

- **No PII Storage**: User queries are logged but no personal identifiers
- **Audit Trail**: Contains questions and answers, but no user IDs by default
- **Data Retention**: Configurable (not implemented, use DB retention policies)
- **GDPR**: Consider adding user data deletion endpoints

## Recommendations for Production

1. **Authentication**: Add JWT or OAuth2
2. **Authorization**: Role-based access control
3. **Encryption**: TLS for all traffic, encrypt sensitive DB fields
4. **Monitoring**: Security event logging (failed auth, suspicious patterns)
5. **WAF**: Web Application Firewall for additional protection
6. **Secrets Rotation**: Automated secret rotation
7. **Audit Logging**: Immutable audit logs (e.g., CloudWatch Logs)
