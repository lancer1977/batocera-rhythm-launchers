# ITGmania portable payload

Do not place an ITGmania binary in this repository. The operator stages the
qualified upstream `ITGmania-1.3.0-Linux-no-songs.tar.gz` at the configured
artifact path. The service verifies its SHA-256 before extracting it into this
bundle's isolated runtime directory.

Place known-good song packs only in this bundle's `Songs/` directory. Sidecar
events remain under this bundle's `events/` directory with the stock
`itgmania-theme-lua` profile.
