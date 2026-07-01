#!/usr/bin/env node

function parseArgs(argv) {
  const args = {};

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === "--help" || arg === "-h") {
      args.help = true;
      continue;
    }

    if (!arg.startsWith("--")) {
      throw new Error(`Unexpected positional argument: ${arg}`);
    }

    const key = arg.slice(2);
    const value = argv[index + 1];

    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }

    args[key] = value;
    index += 1;
  }

  return args;
}

function slugify(value) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function titleize(slug) {
  const acronyms = new Map([
    ["api", "API"],
    ["ec", "EC"],
    ["ui", "UI"]
  ]);

  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => acronyms.get(part) || part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function usage() {
  return `Usage:
  node derive-registry-config.mjs --name "Acme UI" --owner acme [--repo acme-ui-registry] [--namespace acme] [--homepage https://acme.github.io/acme-ui-registry]

Outputs derived registry names, public URLs, and manifest snippets as JSON.`;
}

let args;

try {
  args = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  console.error("");
  console.error(usage());
  process.exit(1);
}

if (args.help) {
  console.log(usage());
  process.exit(0);
}

if (!args.name || !args.owner) {
  console.error("--name and --owner are required.");
  console.error("");
  console.error(usage());
  process.exit(1);
}

const slug = slugify(args.name);

if (!slug) {
  console.error("--name must contain at least one ASCII letter or number after slugging.");
  process.exit(1);
}

const repo = args.repo || `${slug}-registry`;
const namespace = `@${slugify(args.namespace || slug.replace(/-ui$/, ""))}`;
const homepage = args.homepage || `https://${args.owner}.github.io/${repo}`;
const themeItem = `${slug}-theme`;
const themeCss = `${themeItem}.css`;
const title = titleize(slug);
const itemBase = `${homepage.replace(/\/+$/g, "")}/r`;

const output = {
  name: args.name,
  slug,
  title,
  owner: args.owner,
  repo,
  namespace,
  homepage,
  catalogUrl: `${itemBase}/registry.json`,
  templateUrl: `${itemBase}/{name}.json`,
  themeItem,
  themeCss,
  createEcAppArg: `--shadcn-registry ${itemBase}/registry.json`,
  shadcnNamespaceCommand: `npx shadcn@latest registry add ${namespace}=${itemBase}/{name}.json`,
  rootRegistry: {
    $schema: "https://ui.shadcn.com/schema/registry.json",
    name: slug,
    homepage,
    include: [
      "src/lib/registry.json",
      "src/hooks/registry.json",
      "src/theme/registry.json",
      "src/components/ui/registry.json"
    ]
  },
  themeRegistryItem: {
    name: themeItem,
    type: "registry:theme",
    title: `${title} Theme`,
    description: `${title} theme tokens and base Tailwind CSS for registry components.`,
    dependencies: ["tw-animate-css@^1.4.0"],
    css: {
      "@import \"tw-animate-css\"": {},
      [`@import "./${themeCss}"`]: {}
    },
    files: [
      {
        path: themeCss,
        type: "registry:file",
        target: `src/${themeCss}`
      }
    ]
  },
  commonRegistryDependencies: [
    `${itemBase}/${themeItem}.json`,
    `${itemBase}/utils.json`
  ]
};

console.log(JSON.stringify(output, null, 2));
