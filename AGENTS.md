# Valyria Web App

This is the user's independent browser/PWA edition, intended for a fresh season. Do not reintroduce Telegram SDK, Telegram login, foreign CDN dependencies or production database settings from the Telegram edition.

Shared changes must also be applied to the sibling `../caravan-repo` edition per the user's instruction. Authentication, PWA assets and web notification delivery are edition-specific. Never blindly overwrite these files during synchronization. Use explicit commits and review differences.

Read `docs/WEB_APP_FA.md` before deployment. Do not automatically deploy this branch to the existing live Telegram environment or migrate player data into it.
