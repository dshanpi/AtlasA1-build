# AtlasA1 repository layout

The T736 open-board sources are split into four repositories so an Armbian
checkout can consume the board integration without copying build products or
licensed vendor files.

| Repository | Scope |
| --- | --- |
| `AtlasA1-build` | Armbian board/family metadata, reproducible build and packaging scripts, public configuration, tests, and build documentation |
| `AtlasA1-linux` | Linux board patches, kernel configuration, Ethernet/GPU kernel integration, and their build checks |
| `AtlasA1-uboot` | U-Boot and TF-A patches, SPL/LPDDR4x source, boot configuration, and boot-payload tools |
| `AtlasA1-media` | Cedar/OMX/PVR userspace integration, browser transport, media kernel glue patches, media builders, and media validation |

The four repositories intentionally contain source, configuration, tests, and
sanitised manifests only. The following stay outside the public repositories:

- `sources/armbian-build` and other upstream checkouts, which are fetched from
  the pinned commits in `config/sources.lock.json`.
- `build/`, `output/`, `tmp/`, generated packages, raw media, serial captures,
  credentials, and control-service state.
- Tina/DDR/GPU/codec binaries and other files whose redistribution is not
  authorised. Their expected names, versions, and hashes are recorded in the
  input templates and acceptance records.

## Reconstructing the tree

Run the exporter from the `mainline` workspace to create four clean staging
directories. It refuses to delete an existing destination and writes a
`SOURCE-MANIFEST.json` in every directory.

```sh
python3 tools/export_atlas_repositories.py --destination /tmp/atlas-repositories
```

Each staging directory is an independent Git repository. Add the corresponding
remote, review the generated manifest, and commit it to the matching GitHub
repository. The build repository README contains the cross-repository checkout
instructions. A normal Armbian build uses the checked-in board metadata and
the pinned Linux/U-Boot references, then applies the public media integration
when the authorised runtime inputs are supplied.

The exporter does not copy historical build output or claim that unvalidated
hardware paths are production-ready. Media acceptance records retain their
actual scope, including the current CMA and encoder limitations.
