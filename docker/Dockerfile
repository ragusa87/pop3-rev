FROM archlinux:base

RUN pacman -Syu --noconfirm --needed \
        wine xorg-server-xvfb x11vnc xdotool python imagemagick gdb \
    && pacman -Scc --noconfirm

ARG UID=1000
ARG GID=1000
ARG USERNAME=laurent

RUN groupadd -g ${GID} ${USERNAME} \
    && useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER ${USERNAME}
ENV HOME=/home/${USERNAME}
ENV WINEPREFIX=${HOME}/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:99

WORKDIR /work
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
