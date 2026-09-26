import QtQuick
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
    property url screenSource: ""
    property var screenVm: null
    property bool notificationsOpen: false

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
            NumberAnimation { duration: 280; easing.type: Easing.OutCubic }
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
            screenSource: root.screenSource
            screenVm: root.screenVm
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
            visible: themeBridge.miniPlayerVisible && !root.showingNowPlaying
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
}
