# Build and host a browser game

Install the local package with its `web` extra. This project needs no configuration:

```text
my-game/
    main.py
    characters.py
    assets/
        hero.png
        jump.ogg
```

Run `plocks run my-game`, `plocks serve my-game --port 8000`, or
`plocks build my-game`. The launchers use the game root as their working
directory. Relative asset paths always refer to that root, including in supporting
modules. Direct `python main.py` works when started from the root.

## Configuration and collection

An optional `plocks.toml` supports:

```toml
[game]
title = "My Game"
entry = "main.py"
assets = ["assets"]
include = ["credits.txt", "fonts"]
```

Defaults are `main.py`, the project folder's name, and `assets/` when present.
Python files are collected automatically; declare other files explicitly. Hidden
metadata, development environments, bytecode, build output, and node_modules are
excluded. Selected symlinks/junctions, escaping paths, and case-insensitive collisions are
rejected. Unknown `[game]` settings are errors.

Static checks catch identifiable unsupported imports and missing literal asset
paths. Computed paths and dynamic imports remain runtime-checked; a successful
build cannot prove every path or import will work.

## Distribution modes

Default mode uses a pinned external CDN runtime. `plocks build my-game
--self-contained` includes the loader, Python runtime, package resources, fonts,
and supporting files, needing only the hosting origin at playback time. Building
either mode fetches exact artifacts and verifies sizes and SHA-256 digests.
Versioned license notices ship with the package and are also checked against the
runtime inventory before inclusion.

Browser baseline: Pygbag 0.9.3, Python 3.12, pygame-ce 2.5.7, Pillow 11.3.0.
The browser Pillow wheel receives a pinned WebP callback ABI correction; its
input/output hashes and compatibility identifier appear in the build manifest.
Authors using Python 3.13/3.14 should keep shared games compatible with 3.12 syntax
and standard-library APIs. The supported dependency set is Plocks, pygame-ce,
Pillow, local modules, and the standard-library subset supplied by that runtime.
There is no arbitrary PyPI dependency resolver. Threads, processes, native sockets,
desktop UI libraries, and general native extensions are unsupported. Pure Python
helpers can be supplied as local modules, subject to these limits.

Use PNG/JPEG/WebP and OGG/Vorbis. Other known audio formats and non-Vorbis OGG files
are rejected. There is no FFmpeg requirement or automatic transcoding. The page
prepares the runtime, then offers Play before executing game source. This user
interaction enables browser audio. Keep `stage.run()` last; game functions remain
synchronous.

## Outputs and hosting

```text
dist/
    web/
        index.html
        game.apk
        build-manifest.json
        notices/
        ...
    game-web.zip
```

The ZIP matches the website files, with `index.html` at its root. Archive names,
order, and timestamps are normalized. The manifest records package/runtime
versions and included file hashes/sizes, excluding its own hash. Third-party
notices are included. The builder stages copies, never executes game code, and
preserves previous successful output when rebuilding fails.
If the filesystem also prevents rollback, the error reports the backup directory
containing the previous artifacts so they can be restored manually.

Upload `web/` contents or extract the ZIP on a static HTTP(S) host. Relative URLs
support prefixes such as `https://example.com/games/my-game/`. Serve `.wasm` as
`application/wasm`. HTTP compression and caching improve startup. No application
server or special isolation headers are required. `file://` is unsupported.

The 0.2 combined demo transferred about 24 MB from an uncompressed self-contained
server and 12.3 MB using the CDN runtime on a cold load. These are samples, not size or startup-time
guarantees. ZIP disk size differs from HTTP transfer size.

Desktop browsers with WebAssembly are the target. Mobile/touch compatibility,
browser authoring, video export, and persistent saved games are outside this release's
guarantees. Sharing a browser bundle does not make arbitrary source safe to run
on a desktop. No hosting provider integration or deployment runs automatically.
