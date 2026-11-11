# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| main    | yes       |

## Reporting a vulnerability

Do **not** open a public issue for security-sensitive findings.

1. Email the repository owner (see GitHub profile `Job4874`) with subject `[SECURITY] <repo-name>`.
2. Include reproduction steps, impact, and affected paths.
3. Allow up to 7 business days for initial response.

## Scope

This repository is private. Findings in dependencies, CI workflows, or committed secrets are in scope.

## Safe harbor

Good-faith research that avoids data destruction, privacy violations, or service disruption is appreciated.

## Automated scanning

- `opsec.yml` — Gitleaks + suspicious file patterns (required for merge on protected branches)
- `security-gate.yml` — dependency review, Trivy, CodeQL (where enabled)
- `security-artifacts.yml` — Semgrep + Trivy config (advisory)

Local pre-push hooks block common secret paths before push.
