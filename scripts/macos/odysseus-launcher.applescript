property appURL : "http://127.0.0.1:__PORT__"

on run
	my startOdysseus()
end run

on reopen
	my startOdysseus()
end reopen

on idle
	return 60
end idle

on quit
	my stopOdysseus()
	continue quit
end quit

on startOdysseus()
	set launcherScript to "
set -u
UID_NUM=$(id -u)
URL='http://127.0.0.1:__PORT__'
LOG='__INSTALL_DIR__/logs/app-launcher.log'
REPO='__INSTALL_DIR__'
ODYSSEUS_PLIST='__INSTALL_DIR__/com.leounib.projects.odysseus.plist'
OLLAMA_PLIST='__OLLAMA_DIR__/com.leounib.projects.ollama.plist'
mkdir -p '__INSTALL_DIR__/logs'
{
  echo \"[$(date)] Launch requested\"

  ENV_CHOICE=$(/usr/bin/osascript -e 'set envs to {\"dev\", \"nonprod\", \"prod\"}' -e 'set selectedEnv to choose from list envs with prompt \"Select the Odysseus environment to load:\" default items {\"dev\"} with title \"Odysseus\"' -e 'if selectedEnv is false then return \"Cancel\"' -e 'return item 1 of selectedEnv')

  if [ \"$ENV_CHOICE\" = \"Cancel\" ]; then
    echo \"[$(date)] Environment selection cancelled\"
    exit 0
  fi

  case \"$ENV_CHOICE\" in
    dev) BRANCH='leounib-dev' ;;
    nonprod) BRANCH='leounib-nonprod' ;;
    prod) BRANCH='leounib-main' ;;
    *) echo \"[$(date)] Unknown environment: $ENV_CHOICE\"; exit 1 ;;
  esac

  echo \"[$(date)] Selected $ENV_CHOICE ($BRANCH)\"

  launchctl bootout \"gui/$UID_NUM/com.leounib.projects.odysseus\" >/dev/null 2>&1 || true
  ODYSSEUS_PID=$(lsof -ti tcp:__PORT__ 2>/dev/null || true)
  if [ -n \"$ODYSSEUS_PID\" ]; then
    kill $ODYSSEUS_PID >/dev/null 2>&1 || true
  fi

  cd \"$REPO\" || exit 1
  git fetch origin >/dev/null 2>&1 || true
  git switch \"$BRANCH\" >/dev/null 2>&1 || exit 1
  git pull --ff-only origin \"$BRANCH\" >/dev/null 2>&1 || true

  launchctl print \"gui/$UID_NUM/com.leounib.projects.ollama\" >/dev/null 2>&1 || launchctl bootstrap \"gui/$UID_NUM\" \"$OLLAMA_PLIST\" >/dev/null 2>&1 || true
  launchctl enable \"gui/$UID_NUM/com.leounib.projects.ollama\" >/dev/null 2>&1 || true
  launchctl kickstart -k \"gui/$UID_NUM/com.leounib.projects.ollama\" >/dev/null 2>&1 || true

  launchctl print \"gui/$UID_NUM/com.leounib.projects.odysseus\" >/dev/null 2>&1 || launchctl bootstrap \"gui/$UID_NUM\" \"$ODYSSEUS_PLIST\" >/dev/null 2>&1 || true
  launchctl enable \"gui/$UID_NUM/com.leounib.projects.odysseus\" >/dev/null 2>&1 || true
  launchctl kickstart -k \"gui/$UID_NUM/com.leounib.projects.odysseus\" >/dev/null 2>&1 || true

  for i in $(seq 1 90); do
    if curl -s -o /dev/null \"$URL\"; then
      echo \"[$(date)] Ready: $URL\"
      /usr/bin/open \"$URL\" >/dev/null 2>&1 || true
      exit 0
    fi
    sleep 1
  done
  echo \"[$(date)] Timed out waiting for $URL\"
} >> \"$LOG\" 2>&1
"
	«event sysoexec» launcherScript
end startOdysseus

on stopOdysseus()
	set shutdownScript to "
set -u
UID_NUM=$(id -u)
LOG='__INSTALL_DIR__/logs/app-launcher.log'
mkdir -p '__INSTALL_DIR__/logs'
{
  echo \"[$(date)] Quit requested\"
  launchctl bootout \"gui/$UID_NUM/com.leounib.projects.odysseus\" >/dev/null 2>&1 || true
  launchctl bootout \"gui/$UID_NUM/com.leounib.projects.ollama\" >/dev/null 2>&1 || true

  ODYSSEUS_PID=$(lsof -ti tcp:__PORT__ 2>/dev/null || true)
  if [ -n \"$ODYSSEUS_PID\" ]; then
    kill $ODYSSEUS_PID >/dev/null 2>&1 || true
  fi
} >> \"$LOG\" 2>&1
"
	«event sysoexec» shutdownScript
end stopOdysseus
