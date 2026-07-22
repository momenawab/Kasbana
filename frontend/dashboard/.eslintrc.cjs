module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
  ],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  settings: { react: { version: 'detect' } },
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    'react/prop-types': 'off',
    // Allow the destructure-to-omit pattern (`const { name, ...rest } = form`)
    // where a field is pulled out purely to keep it OUT of the rest object.
    'no-unused-vars': ['error', { ignoreRestSiblings: true }],
  },
  ignorePatterns: ['dist', 'node_modules', 'public/mockServiceWorker.js'],
}
