# Manually staged runtime assets

Run `python groove.py prepare --model <exact-model-id>` from the repository root.
It creates every destination directory and prints the immutable download URL for
each required file. It never downloads a model.

After placing the files, run:

```bash
python groove.py verify
```

The verifier checks byte size and SHA-256 against `assets-manifest.json`.

Downloaded model and tokenizer files are ignored by Git. Do not commit them:
the core pack alone is about 269 MiB and each upstream model has its own license.
