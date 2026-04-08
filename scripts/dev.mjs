#!/usr/bin/env node
import { existsSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import concurrently from 'concurrently'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const isWin = process.platform === 'win32'
const python = join(root, 'apps', 'api', '.venv', isWin ? 'Scripts/python' : 'bin/python')

if (!existsSync(join(root, 'apps', 'api', '.venv'))) {
  console.error('Python virtual environment not found at apps/api/.venv')
  console.error('Create one before starting the API.')
  process.exit(1)
}

const qdrantUrl = process.env.WORKBENCH_QDRANT_URL
const useReload = qdrantUrl && qdrantUrl !== 'embedded'

if (!qdrantUrl) {
  console.log('WORKBENCH_QDRANT_URL not set. The API will use embedded Qdrant by default.')
} else if (!useReload) {
  console.log('Embedded Qdrant detected. Starting API without --reload to avoid local storage lock conflicts.')
}

const uvicornCmd = [
  python,
  '-m', 'uvicorn', 'app.main:app',
  ...(useReload ? ['--reload'] : []),
  '--host', '127.0.0.1',
  '--port', '8010',
].join(' ')

const { result } = concurrently(
  [
    {
      command: uvicornCmd,
      name: 'api',
      cwd: join(root, 'apps', 'api'),
      prefixColor: 'cyan',
    },
    {
      command: 'corepack pnpm dev',
      name: 'web',
      cwd: join(root, 'apps', 'web'),
      prefixColor: 'magenta',
    },
  ],
  {
    killOthers: ['failure', 'success'],
    restartTries: 0,
  }
)

result.catch(() => process.exit(1))
