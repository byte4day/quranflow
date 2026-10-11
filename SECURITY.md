# Security

Report a suspected vulnerability privately through GitHub's private vulnerability
reporting feature if enabled for the published repository. Otherwise contact the
repository owner privately before sharing sensitive details. Do not post tokens,
personal configuration or executable exploit payloads in a public issue.

QuranFlow validates MP3Quran recording hosts and HTTPS, verifies TLS certificates,
uses argument arrays, and stores runtime state in a directory owned by the current
user with mode 0700. Its Unix IPC socket and session files use mode 0600. Controls
verify the socket's peer UID/PID and Linux process-start identity before issuing
commands; stored PIDs are never used to terminate arbitrary processes.

mpv IPC is a powerful interface. Do not share the runtime directory or expose the
socket over the network. Use an updated mpv/FFmpeg from your distribution. Normal
requests reveal your IP address and selected stream to the audio provider. QuranFlow
does not send telemetry. Provider redirects and delivery remain under the provider's
control; external availability and recording rights are outside this project.

The user-scoped installer checks ownership markers, tracks file digests, backs up
conflicts and leaves user-edited files intact during uninstall. It does not install
system packages or edit shell profiles. Review local scripts before running them.
