// Scoped to apps/mobile: Biome cannot lint React Native accessibility, so this one workspace has its own
// minimal ESLint config (typescript-eslint + the react-native-a11y rule set). The rest of the repo stays on Biome.
// The plugin declares ESLint <= 8 as a peer; its rules run unchanged on ESLint 10 (a planted unlabeled touchable
// fails the lint, see the mobile-build skill). `has-accessibility-hint` is off: hints belong on controls whose
// result is not obvious from the label, not on every labelled element.
import js from '@eslint/js'
import a11y from 'eslint-plugin-react-native-a11y'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['android/**', 'ios/**', '.expo/**', 'node_modules/**', 'coverage/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'react-native-a11y': a11y },
    rules: {
      // every rule of the plugin's set, forced to error (never a warning that passes the lint)
      ...Object.fromEntries(Object.keys(a11y.configs.all.rules).map((name) => [name, 'error'])),
      'react-native-a11y/has-accessibility-hint': 'off',
    },
  },
)
