module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
  },
  overrides: [
    {
      // auth.tsx exports both a component and a hook — react-refresh rule doesn't apply to lib files
      files: ['src/lib/**'],
      rules: {
        'react-refresh/only-export-components': 'off',
      },
    },
  ],
}
