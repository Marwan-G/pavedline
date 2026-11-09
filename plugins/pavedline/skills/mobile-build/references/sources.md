# Sources and pins for mobile-build

Checked 2026-11-09. Every pin is exact (no `^` or `~`) and at least two weeks old (published on or before 2026-10-26); `pnpm-workspace.yaml` `minimumReleaseAge: 20160` makes pnpm refuse a younger transitive package (it refused `eslint@10.14.0` and `typescript-eslint@8.72.1` on the first install, so those two are one release back). Facts at a date: re-check before bumping. The whole stack's pin table is `stacks/nextjs-fastapi/SOURCES.md`.

## Expo SDK and its table

Newest SDK is 58. The newest `expo` (58.0.23, 2026-11-03) and 58.0.20 to 58.0.22 are under two weeks, so the pin is `expo@58.0.19` (2026-10-23). The matching versions are the ones in that release's `bundledNativeModules.json` (npm tarball `expo-58.0.19.tgz`, read 2026-11-09): `react@19.3.0`, `react-native@0.88.0`, `expo-constants ~58.0.13`, `expo-status-bar ~58.0.4`, `jest-expo ~58.0.12`.

| Pin | Published | URL |
|---|---|---|
| `expo@58.0.19` | 2026-10-23 | https://www.npmjs.com/package/expo/v/58.0.19 |
| `react-native@0.88.0` | 2026-10-15 | https://www.npmjs.com/package/react-native/v/0.88.0 |
| `react@19.3.0` (the web app is on 19.3.1; pnpm's isolated install keeps both) | 2026-09-09 | https://www.npmjs.com/package/react/v/19.3.0 |
| `expo-constants@58.0.13` | 2026-10-21 | https://www.npmjs.com/package/expo-constants/v/58.0.13 |
| `expo-status-bar@58.0.4` | 2026-10-21 | https://www.npmjs.com/package/expo-status-bar/v/58.0.4 |
| `jest-expo@58.0.12` | 2026-10-21 | https://www.npmjs.com/package/jest-expo/v/58.0.12 |
| `@react-native/jest-preset@0.88.0` (peer of jest-expo) | 2026-10-15 | https://www.npmjs.com/package/@react-native/jest-preset/v/0.88.0 |
| `test-renderer@1.3.0` (peer of testing-library 14) | 2026-09-17 | https://www.npmjs.com/package/test-renderer/v/1.3.0 |
| `@testing-library/react-native@14.1.0` | 2026-10-08 | https://www.npmjs.com/package/@testing-library/react-native/v/14.1.0 |
| `jest@30.5.2`, `@types/jest@30.0.0` | 2026-09-18, 2025-06-16 | https://www.npmjs.com/package/jest/v/30.5.2 |
| `eslint@10.13.0` | 2026-10-16 | https://www.npmjs.com/package/eslint/v/10.13.0 |
| `typescript-eslint@8.72.0` | 2026-10-19 | https://www.npmjs.com/package/typescript-eslint/v/8.72.0 |
| `@eslint/js@9.39.5` | 2026-07-10 | https://www.npmjs.com/package/@eslint/js/v/9.39.5 |
| `eslint-plugin-react-native-a11y@3.5.1` | 2024-11-04 | https://www.npmjs.com/package/eslint-plugin-react-native-a11y/v/3.5.1 |
| `@types/react@19.3.0`, `typescript@5.9.3` | 2026-09-09, 2025-09-30 | same pins as the web app |

- **a11y plugin on ESLint 10.** `eslint-plugin-react-native-a11y@3.5.1` is the newest release of the original plugin (unmaintained since 2024) and declares `eslint ^3 || ... || ^8` as a peer, so pnpm prints an unmet-peer notice. Its rules run unchanged on ESLint 10 flat config (verified 2026-11-09: a planted `Pressable` with no role or label fails with `has-valid-accessibility-descriptors`; the clean app passes). Biome has no equivalent. Fallback if it ever stops working: the fork https://github.com/Volksverpetzer/eslint-plugin-react-native-a11y, npm `@volksverpetzer/eslint-plugin-react-native-a11y` `3.6.0`, last release 2026-09-24 (https://www.npmjs.com/package/@volksverpetzer/eslint-plugin-react-native-a11y, checked 2026-11-09; peer ESLint `^3 ... ^10`). Not adopted: the original is pinned and tested, and a fork is a second dependency to vet. `has-accessibility-hint` is turned off on purpose (a hint on every labelled element is noise).
- **pnpm and Expo.** https://docs.expo.dev/guides/monorepos/ (2026-11-09): "From SDK 54, Expo supports isolated dependencies and isolated installations", "For pnpm, this is the default installation strategy"; no `.npmrc` or `node-linker` setting needed; no manual Metro configuration when the config comes from `expo/metro-config`; `nodeLinker: hoisted` is the fallback if a native build ever fails on isolated installs. `pnpm-workspace.yaml` therefore only gained `allowBuilds` (both install scripts, `@parcel/watcher` and `unrs-resolver`, stay disabled; both ship prebuilt binaries).
- **Build requirements.** https://docs.expo.dev/get-started/set-up-your-environment/ (2026-11-09): JDK 17; Android SDK Platform 36 ("Android 16 (Baklava) SDK is required to compile a React Native app"); Xcode from the Mac App Store. The Gradle wrapper `expo prebuild` generates is Gradle 9.4.1.
- **`expo prebuild`.** https://docs.expo.dev/workflow/prebuild/ ; `--no-install` skips the package install (and `pod install` on iOS), `--platform android|ios`, `--clean` regenerates the folder. Run on this repository's pack on 2026-11-09: both platforms generate (`android/` with the Gradle wrapper, `ios/Example.xcodeproj`).

## Ruling 8: macOS runners and public repositories

https://docs.github.com/en/actions/reference/runners/github-hosted-runners (2026-11-09): "Use of the standard GitHub-hosted runners is free and unlimited on public repositories." The public-repository table lists Linux, Windows, Linux arm64, Windows arm64 and macOS Intel (`macos-15-intel`, `macos-26-intel`) and arm64 M1 (`macos-latest`, `macos-15`, `macos-26`; 3 CPU, 7 GB, 14 GB SSD). Larger runners are billed. https://docs.github.com/en/billing/concepts/product-billing/github-actions (2026-11-09) lists "Standard GitHub-hosted runners in public repositories" among usage that "remains free independently" and gives per-minute rates for macOS in private repositories. Consequence: the unsigned iOS simulator build runs in a public repository; in a private one it needs the founder's cost approval.

## Not verified here (marked, never guessed)

- The Xcode version on `macos-26` and the exact `xcodebuild` scheme and workspace names: they come from the generated project (`<App>.xcworkspace`, scheme `<App>`); the CI job reads them from `ls ios/*.xcworkspace` and `xcodebuild -list`.
- The iOS and Android native builds were not run on this machine (no Xcode, no JDK, no Android SDK); they are proven in CI.
- App Store Connect API key upload mechanics and Google Play upload: founder steps, deliberately not scripted.
