# MeowTOrrent

An independent local torrent application with a React interface and an embedded
libtorrent 2.0 engine. No qBittorrent, Web UI, account, or hosted backend required.

## Run

Install Node.js 22.13+ and Python 3.11–3.13, then:

```sh
npm install
npm run local
```

Open http://localhost:5173. The launcher sets up the Python engine dependencies
on first use, starts both processes, and the interface connects automatically.
Downloads go to `~/Downloads/MeowTOrrent`; state goes to `~/.meowtorrent`.
Use `MEOW_DOWNLOADS` and `MEOW_STATE` to override those locations.

Magnet links, torrent files, v1, v2, hybrid, and multi-file torrents are supported
by libtorrent. Downloads depend on reachable peers and trackers. This is not a
promise of universal torrent availability or complete µTorrent feature parity.

Pause/resume and library persistence are supported. Restarting rechecks existing
pieces before resuming. Removing a torrent always keeps files. The backend must
remain running for transfers. The API accepts only the local UI origin and uses
an ephemeral session token. The program is a local web app, not a desktop binary.

## Development

`npm run dev` starts only the interface. `npm run build` builds the interface.
`npm run test:engine` runs local engine integration tests after initial setup.
See [the setup guide](public/engine-guide.txt) for details.

The engine uses [libtorrent](https://www.libtorrent.org/), licensed under BSD-3-Clause.
