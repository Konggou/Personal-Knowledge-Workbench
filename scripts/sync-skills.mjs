#!/usr/bin/env node
import { mkdirSync, existsSync, cpSync, rmSync, readdirSync, statSync } from 'fs'
import { join, basename } from 'path'
import { tmpdir, homedir } from 'os'
import { execSync } from 'child_process'
import { randomUUID } from 'crypto'

// Parse args: --repo --ref --dest --keep-temp
const args = process.argv.slice(2)
function getArg(name, defaultVal) {
  const idx = args.indexOf(name)
  return idx !== -1 ? args[idx + 1] : defaultVal
}

const repoUrl = getArg('--repo', 'https://github.com/Konggou/my_skills.git')
const ref = getArg('--ref', 'main')
const destination = getArg('--dest', join(homedir(), '.codex', 'skills'))
const keepTemp = args.includes('--keep-temp')

try {
  execSync('git --version', { stdio: 'ignore' })
} catch {
  console.error('git is required but was not found in PATH.')
  process.exit(1)
}

mkdirSync(destination, { recursive: true })

const tempRoot = join(tmpdir(), `codex-skills-sync-${randomUUID()}`)
const backupRoot = join(tmpdir(), `codex-skills-backup-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}`)

console.log(`Cloning ${repoUrl} ...`)
execSync(`git clone --depth 1 --branch ${ref} --recurse-submodules ${repoUrl} "${tempRoot}"`, { stdio: 'inherit' })

function findSkillDirs(root) {
  const results = []
  function walk(dir) {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry)
      if (!statSync(full).isDirectory()) continue
      if (entry === 'template') continue
      if (existsSync(join(full, 'SKILL.md'))) {
        results.push(full)
      } else {
        walk(full)
      }
    }
  }
  walk(root)
  return results.sort((a, b) => basename(a).localeCompare(basename(b)))
}

const skills = findSkillDirs(tempRoot)
if (skills.length === 0) {
  console.error(`No skills with SKILL.md were found in ${repoUrl}.`)
  rmSync(tempRoot, { recursive: true, force: true })
  process.exit(1)
}

mkdirSync(backupRoot, { recursive: true })

const created = []
const updated = []

for (const skillDir of skills) {
  const name = basename(skillDir)
  const target = join(destination, name)

  if (existsSync(target)) {
    cpSync(target, join(backupRoot, name), { recursive: true })
    rmSync(target, { recursive: true, force: true })
    updated.push(name)
  } else {
    created.push(name)
  }

  cpSync(skillDir, target, { recursive: true })
}

console.log()
console.log('Skills sync complete.')
console.log(`Destination: ${destination}`)
console.log(`Created: ${created.length}`)
if (created.length > 0) console.log(`  ${created.join(', ')}`)
console.log(`Updated: ${updated.length}`)
if (updated.length > 0) console.log(`  ${updated.join(', ')}`)
console.log(`Backup: ${backupRoot}`)

if (!keepTemp) {
  rmSync(tempRoot, { recursive: true, force: true })
} else {
  console.log(`Temporary clone kept at: ${tempRoot}`)
}

console.log('Restart Codex to pick up new skills.')
