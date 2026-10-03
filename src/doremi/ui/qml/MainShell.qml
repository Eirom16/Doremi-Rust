import QtQuick
import QtQuick.Window
import QtQuick.Controls
import Doremi 1.0

Item {
    id: root

    property var navigationController: null
    property var headerController: null
    property var offlineController: null
    property var notificationController: null
    property var playerController: null
    property var toastController: null
    property var closeController: null
    property var commandController: null
    function editorFocused() {
        var item = root.Window.window ? root.Window.window.activeFocusItem : null
        while (item) {
            if (item.readOnly !== undefined && !item.readOnly) return true
            item = item.parent
        }
        return false
    }
    CommandPalette { id: commandPalette; controller: root.commandController }
    PlaylistPicker { controller: typeof desktopController !== "undefined" ? desktopController : null }
    DropArea {
        anchors.fill: parent
        z: 20
        onEntered: function(drag) { drag.accepted = drag.hasUrls }
        onDropped: function(drop) {
            if (drop.hasUrls && typeof desktopController !== "undefined" && desktopController) {
                var urls = []
                for (var i = 0; i < drop.urls.length; ++i) urls.push(drop.urls[i].toString())
                desktopController.import_files(urls)
                drop.acceptProposedAction()
            }
        }
        Rectangle {
            anchors.fill: parent
            visible: parent.containsDrag
            color: "transparent"
            border.width: 3
            border.color: themeBridge.colors["accent"]
        }
    }
    Shortcut { sequence: "Ctrl+K"; enabled: root.commandController !== null; onActivated: commandPalette.open() }
    Shortcut { sequence: "Ctrl+P"; enabled: root.commandController !== null && !root.editorFocused() && !commandPalette.opened; onActivated: root.commandController.execute("now_playing") }
    Shortcut { sequence: "Ctrl+Right"; enabled: root.commandController !== null && !root.editorFocused() && !commandPalette.opened; onActivated: root.commandController.execute("next") }
    Shortcut { sequence: "Ctrl+Left"; enabled: root.commandController !== null && !root.editorFocused() && !commandPalette.opened; onActivated: root.commandController.execute("previous") }
    Shortcut { sequence: "L"; enabled: root.commandController !== null && !root.editorFocused() && !commandPalette.opened; onActivated: root.commandController.execute("like") }
    Shortcut { sequence: "Space"; enabled: root.commandController !== null && !root.editorFocused() && !commandPalette.opened; onActivated: root.commandController.execute("play") }
    property bool notificationsOpen: false
    property bool closeConfirmationVisible: false
    property int activeDownloadCount: 0

    readonly property int expandedSidebarWidth: 214
    readonly property int collapsedSidebarWidth: 64
    readonly property int sidebarWidth: navigationController && navigationController.collapsed
                                       ? collapsedSidebarWidth : expandedSidebarWidth
    readonly property int headerHeight: 68
    readonly property int offlineHeight: offlineController && offlineController.shown ? 54 : 0
    readonly property bool showingNowPlaying: navigationController
                                             && navigationController.activeRoute === "now_playing"

    Rectangle {
        anchors.fill: parent
        color: themeBridge.colors["bg_base"]
    }

    NavigationSidebar {
        id: navigation
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: root.sidebarWidth
        navigationController: root.navigationController

        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    Item {
        id: content
        anchors.left: navigation.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        HeaderBar {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: root.headerHeight
            headerController: root.headerController
        }

        SearchSuggestions {
            id: suggestions
            x: header.searchX
            y: header.height + Theme.spacingXxs
            width: header.searchWidth
            height: Math.min(360, Math.max(64,
                (root.headerController ? root.headerController.suggestions.length : 0) * 54 + 12))
            visible: root.headerController && root.headerController.query.length > 0
                     && root.headerController.suggestions.length > 0
            z: 4
            headerController: root.headerController
        }

        OfflineBanner {
            id: offlineBanner
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            height: root.offlineHeight
            offlineController: root.offlineController

            Behavior on height {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }
        }

        ScreenHost {
            id: screenHost
            objectName: "screenHost"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: offlineBanner.bottom
            anchors.bottom: parent.bottom
        }

        NotificationPanel {
            id: notifications
            anchors.top: header.bottom
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: root.notificationsOpen ? 360 : 0
            visible: width > 0
            clip: true
            notificationController: root.notificationController

            Behavior on width {
                NumberAnimation { duration: 250; easing.type: Easing.OutCubic }
            }
        }

        MiniPlayer {
            id: miniPlayer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: Theme.spacingMd
            anchors.rightMargin: Theme.spacingMd
            anchors.bottom: parent.bottom
            height: 88
            // Se mantiene en escena hasta terminar la salida, para que no
            // desaparezca de golpe. Al activarse se desliza desde debajo de
            // la ventana; antes de la primera reproducción permanece vacío e
            // invisible.
            readonly property bool shouldShow: themeBridge.miniPlayerVisible
                                              && !root.showingNowPlaying
            visible: shouldShow || opacity > 0
            opacity: shouldShow ? 1 : 0
            transform: Translate {
                y: miniPlayer.shouldShow ? 0 : miniPlayer.height + Theme.spacingMd
                Behavior on y {
                    NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
            }
            z: 2
            playerController: root.playerController
        }

        Toast {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.rightMargin: Theme.spacingLg
            anchors.bottomMargin: Theme.spacingXxl
            width: 380
            z: 8
            toastVm: root.toastController
        }
    }

    ModalDialog {
        id: closeConfirmation
        dialogTitle: "Descargas activas"
        confirmText: "Salir"
        cancelText: "Cancelar"
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        contentItemData: [
            Text {
                width: 360
                text: "Hay " + root.activeDownloadCount
                      + " descargas en curso o en cola. ¿Salir de todos modos?"
                wrapMode: Text.WordWrap
                color: themeBridge.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeBody
            }
        ]

        onConfirmed: root.closeController.confirm_close_with_downloads()
        onCancelled: root.closeController.cancel_close_with_downloads()
        onClosed: {
            if (root.closeConfirmationVisible)
                root.closeController.cancel_close_with_downloads()
        }
    }

    onCloseConfirmationVisibleChanged: {
        if (closeConfirmationVisible)
            closeConfirmation.open()
        else
            closeConfirmation.close()
    }
}
