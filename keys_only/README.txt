Place private_demo.pem here (run ./gen_keys.sh on a trusted machine, then scp the file to this server).
Set DEMO_BANGO_PII_DECRYPT_PEM in .env if you use a custom path. Not required for Bango to load pages; required for /api/demo/register to decrypt PII.
