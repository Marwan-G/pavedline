import type { ExpoConfig } from 'expo/config'

// Placeholders: step 6 replaces the name, slug and identifiers. No signing material, no EAS project id and no store
// configuration lives in this repository (see the mobile-build skill).
const config: ExpoConfig = {
  name: 'Example',
  slug: 'example',
  version: '0.1.0',
  orientation: 'portrait',
  ios: { bundleIdentifier: 'com.example.app', supportsTablet: false },
  android: { package: 'com.example.app' },
  extra: {
    // Public configuration only (it ships inside the app). The API base URL is set per build.
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
  },
}

export default config
