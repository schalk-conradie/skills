#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';

const { values: options } = parseArgs({
	options: {
		name: { type: 'string' },
		directory: { type: 'string' },
		ref: { type: 'string', default: 'boilerplate-v2' },
		source: {
			type: 'string',
			default: 'https://dev.azure.com/Dataloop-Global/Dataloop%20Boilerplate/_git/Dataloop%20Boilerplate'
		},
		help: { type: 'boolean', default: false }
	}
});

if (options.help) {
	console.log(
		'node create-project.mjs --name my-app --directory path [--ref branch-or-tag] [--source trusted-git-url]'
	);
	process.exit(0);
}

if (process.versions.node.split('.')[0] !== '24') {
	throw new Error('Dataloop project creation requires Node 24.');
}

if (!options.name || !options.directory) {
	throw new Error('Provide --name and --directory.');
}

if (!options.ref || options.ref.startsWith('-')) {
	throw new Error('Invalid template ref.');
}

const destination = path.resolve(options.directory);
const temporary = await mkdtemp(path.join(tmpdir(), 'dataloop-project-skill-'));
const template = path.join(temporary, 'template');

try {
	execFileSync('git', ['clone', '--depth', '1', '--branch', options.ref, '--', options.source, template], {
		stdio: 'inherit'
	});

	// Keep generation owned by the initializer in the selected template snapshot.
	execFileSync(
		process.execPath,
		[
			path.join(template, 'scripts/create-project.mjs'),
			'--name',
			options.name,
			'--directory',
			destination,
			'--source',
			template,
			'--ref',
			options.ref
		],
		{ stdio: 'inherit' }
	);
} finally {
	await rm(temporary, { recursive: true, force: true });
}
