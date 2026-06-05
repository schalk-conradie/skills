# Command Palette Development Docs Map

Use this file as the fast path back into the Microsoft PowerToys Command Palette extension documentation.

## Core Microsoft Learn Links

- Command Palette extension development landing page: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/extension-development
- How extensions work / extensibility overview: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/extensibility-overview
- Getting started / creating an extension: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/creating-an-extension
- Adding commands: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/adding-commands
- Publishing extensions: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/publish-extension
- Extension samples: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/samples
- SDK namespaces: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/sdk-namespaces

## API References

- `Microsoft.CommandPalette.Extensions`: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/microsoft-commandpalette-extensions
- `Microsoft.CommandPalette.Extensions.Toolkit`: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/microsoft-commandpalette-extensions-toolkit

## GitHub Sources

- PowerToys repository: https://github.com/microsoft/PowerToys
- Command Palette samples are linked from the samples page and may be fresher than the prose docs.

## Mental Model

- Extensions are standalone .NET applications.
- Command Palette discovers installed packages through the Windows Package Catalog.
- The package manifest declares a `windows.appExtension` named `com.microsoft.commandpalette`.
- The generated template handles most COM server plumbing; avoid hand-editing COM details unless discovery is broken.
- Each extension implements `IExtension`, returning an `ICommandProvider`.
- The command provider exposes top-level commands, fallback commands, context menu items, pages, and settings.
- Supported page styles include list, detail, form, markdown, and grid pages.

## Template Project Shape

The generated project usually includes:

- `Directory.Build.props`
- `Directory.Packages.props`
- `nuget.config`
- `<ExtensionName>.sln`
- `<ExtensionName>/app.manifest`
- `<ExtensionName>/Package.appxmanifest`
- `<ExtensionName>/Program.cs`
- `<ExtensionName>/<ExtensionName>.cs`
- `<ExtensionName>/<ExtensionName>CommandsProvider.cs`
- `<ExtensionName>/Pages/<ExtensionName>Page.cs`
- `<ExtensionName>/Assets/*`
- `<ExtensionName>/Properties/launchSettings.json`
- `<ExtensionName>/Properties/PublishProfiles/*.pubxml`

## Development Checklist

1. Scaffold from Command Palette with `Create a new extension` unless the repo already exists.
2. Keep extension class names valid C# identifiers; display names can be human-readable.
3. Add user-visible commands through page `GetItems()` implementations and command provider wiring.
4. Use toolkit helpers for common commands before writing custom command classes.
5. Deploy through Visual Studio for local testing.
6. Run the Command Palette reload command after deployment.
7. Test from the palette, not only from Visual Studio.
8. For publish/distribution work, re-check the publish docs because packaging guidance may change.

## Frequent Fix Areas

- Missing extension in palette: confirm deployed package, `Package.appxmanifest`, app extension name, COM CLSID consistency, and reload.
- Changed command not visible: redeploy the package and run the reload command.
- Debug output missing: confirm Debug configuration, attach/run under Visual Studio, and inspect the Debug output pane.
- Clone cannot deploy: check that deployment profiles and launch settings were not ignored.
