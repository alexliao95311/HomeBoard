# Local secrets

Place the Firebase service-account JSON file in this directory, then set
`GOOGLE_APPLICATION_CREDENTIALS` in the repository `.env` file to its mounted
container path:

```text
/run/secrets/<your-service-account-filename>.json
```

JSON credential files in this directory are ignored by Git. Never commit or
share the service-account private key.
