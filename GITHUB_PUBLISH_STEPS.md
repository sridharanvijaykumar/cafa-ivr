# Publish CAFA-IVR to GitHub

Recommended repository name: **cafa-ivr**

## Option A — GitHub website + local Git

1. On GitHub.com choose **New repository**.
2. Repository name: `cafa-ivr`.
3. Choose **Public** if you want external teams to discover/adopt it.
4. Do **not** initialize with a README, .gitignore, or license because this folder already contains them.
5. Create the repository.
6. In a terminal inside this folder run:

```bash
git init
git add .
git commit -m "Release CAFA-IVR v1.0.0"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/cafa-ivr.git
git push -u origin main
```

7. On GitHub, open **Releases → Draft a new release**.
8. Tag: `v1.0.0`.
9. Title: `CAFA-IVR v1.0.0`.
10. Attach the release ZIP if desired and summarize the framework, measured validation, and scope limitations.

## Option B — GitHub Desktop

1. Unzip this repository.
2. GitHub Desktop → **Add an Existing Repository from your Hard Drive**.
3. If prompted, create the repository in this folder.
4. Commit all files with message `Release CAFA-IVR v1.0.0`.
5. Choose **Publish repository** and make it public.

## Recommended repository settings

After publishing:

- Enable **Issues** and **Discussions**.
- Add topics: `asr`, `ivr`, `conversational-ai`, `speech-recognition`, `nlu`, `testing`, `contact-center`, `wer`.
- Put `docs/CAFA-IVR_SPEC_v1.0.pdf` in the About/README links when possible.
- Enable branch protection after collaborators begin contributing.
- Create a GitHub Release for every specification version.

## Suggested About text

> Vendor-neutral counterfactual testing framework for attributing ASR-induced failures in conversational IVR. Measures WER, ASR-IFR, CEER and downstream task impact.
