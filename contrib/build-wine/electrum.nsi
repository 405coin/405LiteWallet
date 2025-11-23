

  !include "TextFunc.nsh"
  !include "MUI2.nsh"




  !define PRODUCT_NAME "Electrum"
  !define PRODUCT_WEB_SITE "https://github.com/spesmilo/electrum"
  !define PRODUCT_PUBLISHER "Electrum Technologies GmbH"
  !define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"





  Name "${PRODUCT_NAME}"
  OutFile "dist/electrum-setup.exe"


  InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"


  InstallDirRegKey HKCU "Software\${PRODUCT_NAME}" ""


  RequestExecutionLevel admin


  CRCCheck on


  ShowInstDetails show


  ShowUninstDetails show


  InstallColors /windows


  SetCompressor /SOLID lzma


  SetCompressorDictSize 64


  BrandingText "${PRODUCT_NAME} Installer v${PRODUCT_VERSION}"


  Caption "${PRODUCT_NAME}"


  VIProductVersion 1.0.0.0


  VIAddVersionKey ProductName "${PRODUCT_NAME} Installer"
  VIAddVersionKey Comments "The installer for ${PRODUCT_NAME}"
  VIAddVersionKey CompanyName "${PRODUCT_NAME}"
  VIAddVersionKey LegalCopyright "2013-2018 ${PRODUCT_PUBLISHER}"
  VIAddVersionKey FileDescription "${PRODUCT_NAME} Installer"
  VIAddVersionKey FileVersion ${PRODUCT_VERSION}
  VIAddVersionKey ProductVersion ${PRODUCT_VERSION}
  VIAddVersionKey InternalName "${PRODUCT_NAME} Installer"
  VIAddVersionKey LegalTrademarks "${PRODUCT_NAME} is a trademark of ${PRODUCT_PUBLISHER}"
  VIAddVersionKey OriginalFilename "${PRODUCT_NAME}.exe"




  !define MUI_ABORTWARNING
  !define MUI_ABORTWARNING_TEXT "Are you sure you wish to abort the installation of ${PRODUCT_NAME}?"

  !define MUI_ICON "..\..\electrum\gui\icons\electrum.ico"




  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES




  !insertmacro MUI_LANGUAGE "English"




!macro CreateEnsureNotRunning prefix operation

Function ${prefix}EnsureNotRunning

  Pop $R0

  IfFileExists "$R0" 0 nodir

    FindFirst $1 $2 "$R0\*.exe"
    IfErrors noexe 0

    checkloop:

    !if "${prefix}" == "un."
        StrCmp $2 "Uninstall.exe" skipfile 0
    !endif


    retryopen:
    FileOpen $0 "$R0\$2" a
    IfErrors 0 closeexe
      MessageBox MB_RETRYCANCEL "Can not ${operation} because $2 is still running. Close it and retry." /SD IDCANCEL IDRETRY retryopen
      FindClose $1
      Abort
    closeexe:
    FileClose $0

    skipfile:

    FindNext $1 $2
    IfErrors done 0
    Goto checkloop

    done:
    FindClose $1

  noexe:
  nodir:
FunctionEnd

!macroend


!insertmacro CreateEnsureNotRunning "" "install"
!insertmacro CreateEnsureNotRunning "un." "uninstall"





Function .onInit
	UserInfo::GetAccountType
	pop $0
	${If} $0 != "admin"
		MessageBox mb_iconstop "Administrator rights required!"
		SetErrorLevel 740
		Quit
	${EndIf}


  ReadRegStr $R0 HKCU "Software\${PRODUCT_NAME}" ""
  IfErrors noinstdir 0
    Push $R0
    Call EnsureNotRunning
  noinstdir:
  ClearErrors
FunctionEnd

Section
  SetOutPath $INSTDIR


  RMDir /r "$INSTDIR\*.*"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\*.*"


  File /r "dist\electrum\*.*"
  File "..\..\electrum\gui\icons\electrum.ico"


  WriteRegStr HKCU "Software\${PRODUCT_NAME}" "" $INSTDIR


  DetailPrint "Creating uninstaller..."
  WriteUninstaller "$INSTDIR\Uninstall.exe"


  DetailPrint "Creating desktop shortcut..."
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\electrum-${PRODUCT_VERSION}.exe" ""


  DetailPrint "Creating start-menu items..."
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\electrum-${PRODUCT_VERSION}.exe" "" "$INSTDIR\electrum-${PRODUCT_VERSION}.exe" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME} Testnet.lnk" "$INSTDIR\electrum-${PRODUCT_VERSION}.exe" "--testnet" "$INSTDIR\electrum-${PRODUCT_VERSION}.exe" 0



  WriteRegStr HKCU "Software\Classes\bitcoin" "" "URL:bitcoin Protocol"
  WriteRegStr HKCU "Software\Classes\bitcoin" "URL Protocol" ""
  WriteRegStr HKCU "Software\Classes\bitcoin" "DefaultIcon" "$\"$INSTDIR\electrum.ico, 0$\""
  WriteRegStr HKCU "Software\Classes\bitcoin\shell\open\command" "" "$\"$INSTDIR\electrum-${PRODUCT_VERSION}.exe$\" $\"%1$\""
  WriteRegStr HKCU "Software\Classes\lightning" "" "URL:lightning Protocol"
  WriteRegStr HKCU "Software\Classes\lightning" "URL Protocol" ""
  WriteRegStr HKCU "Software\Classes\lightning" "DefaultIcon" "$\"$INSTDIR\electrum.ico, 0$\""
  WriteRegStr HKCU "Software\Classes\lightning\shell\open\command" "" "$\"$INSTDIR\electrum-${PRODUCT_VERSION}.exe$\" $\"%1$\""


  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\electrum.ico"


  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd







Section "Uninstall"
  RMDir /r "$INSTDIR\*.*"

  RMDir "$INSTDIR"

  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\*.*"
  RMDir  "$SMPROGRAMS\${PRODUCT_NAME}"

  DeleteRegKey HKCU "Software\Classes\bitcoin"
  DeleteRegKey HKCU "Software\${PRODUCT_NAME}"
  DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
SectionEnd

Function UN.onInit

  Push $INSTDIR
  Call un.EnsureNotRunning
FunctionEnd
