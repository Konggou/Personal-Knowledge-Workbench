#!/usr/bin/env node
import { mkdirSync, existsSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { spawn } from 'child_process'
import { execSync } from 'child_process'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const storagePath = join(root, 'data', 'qdrant')

mkdirSync(storagePath, { recursive: true })

let qdrantBin = process.env.WORKBENCH_QDRANT_BIN

if (!qdrantBin) {
  try {
    qdrantBin = execSync('which qdrant 2>/dev/null || where qdrant 2>nul', { encoding: 'utf8' }).trim()
  } catch {
    qdrantBin = null
  }
}

if (!qdrantBin || !existsSync(qdrantBin)) {
  console.log('Qdrant binary not found.')
  console.log('No action is required for the default embedded mode.')
  console.log('Only install or start an external Qdrant binary if you want WORKBENCH_QDRANT_URL to point to a standalone server.')
  console.log('Set WORKBENCH_QDRANT_BIN to the qdrant executable path, or add qdrant to PATH, then rerun this script.')
  process.exit(0)
}

console.log(`Starting Qdrant with storage path: ${storagePath}`)

const child = spawn(qdrantBin, ['--storage-path', storagePath], { stdio: 'inherit' })
child.on('exit', (code) => process.exit(code ?? 0))
