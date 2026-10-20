POP_BIN="D3DPOPTB.EXE"
for dir in \
    ~/.wine/drive_c/"Program Files (x86)"/Bullfrog/"Populous - A l'aube de la création" \
    ~/.wine/drive_c/"GOG Games"/"Populous 3"
do
    if [ -f "${dir}/${POP_BIN}" ]; then
        wine "${dir}/${POP_BIN}"
        exit $?
    fi
done

echo "run_pop.sh: no Populous install found" >&2
exit 1
