!macro NSIS_HOOK_PREINSTALL
  !insertmacro CheckIfAppIsRunning "bot-ofertas-desktop.exe" "Bot de Ofertas"
  DetailPrint "Encerrando componentes do Bot de Ofertas..."
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM bot-ofertas-backend.exe'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM bot-ofertas-whatsapp.exe'
!macroend
