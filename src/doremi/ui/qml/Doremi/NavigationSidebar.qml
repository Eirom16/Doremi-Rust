import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // Compatibilidad con la isla actual; MainShell inyectará esta propiedad.
    property var navigationController: null
    // The sidebar may survive one event-loop turn after its Python controller
    // has been deleted during shutdown.  Keep all bindings total in that
    // window instead of dereferencing a null QObject.
    readonly property bool controllerAvailable: navigationController !== null
    readonly property bool sidebarCollapsed: controllerAvailable
                                           ? navigationController.collapsed : false
    readonly property string activeRoute: controllerAvailable
                                         ? navigationController.activeRoute : ""
    readonly property string activePath: controllerAvailable
                                        ? navigationController.activePath : ""
    readonly property var playlists: controllerAvailable
                                   ? navigationController.playlists : []
    readonly property url appIconSource: controllerAvailable
                                         ? navigationController.appIconSource : ""
    readonly property var colors: themeBridge.colors
    readonly property color accentColor: colors["accent"]
    readonly property string iconFont: "Material Symbols Rounded"

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 6
        anchors.rightMargin: 6
        anchors.topMargin: Theme.spacingSm
        anchors.bottomMargin: Theme.spacingMd
        spacing: 4

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.bottomMargin: Theme.spacingSm

            Image {
                // El isotipo identifica la navegación contraída. En la barra
                // expandida el wordmark basta y evita repetir visualmente la “D”.
                visible: root.sidebarCollapsed
                width: 44
                height: 44
                anchors.centerIn: parent
                source: root.appIconSource
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }

            Label {
                visible: !root.sidebarCollapsed
                text: "Doremi"
                color: root.colors["accent"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeHeading
                font.weight: Font.Bold
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
            }
        }

        Label {
            visible: !root.sidebarCollapsed
            text: "Navegación"
            color: root.colors["text_secondary"]
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeCaption
            font.weight: Font.Medium
            Layout.leftMargin: Theme.spacingSm
            Layout.topMargin: Theme.spacingXxs
            Layout.bottomMargin: Theme.spacingXxs
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "home"
            icon: "home"
            label: "Inicio"
            active: root.activeRoute === route
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "library"
            icon: "library_music"
            label: "Biblioteca"
            active: root.activeRoute === route
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "history"
            icon: "history"
            label: "Historial"
            active: root.activeRoute === route
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "stats"
            icon: "bar_chart"
            label: "Estadísticas"
            active: root.activeRoute === route
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "downloads"
            icon: "download"
            label: "Descargas"
            active: root.activeRoute === route
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "settings"
            icon: "settings"
            label: "Ajustes"
            active: root.activeRoute === route
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            Layout.topMargin: Theme.spacingSm
            spacing: 4

            Label {
                visible: !root.sidebarCollapsed
                text: "Acceso rápido"
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeCaption
                font.weight: Font.Medium
                Layout.leftMargin: Theme.spacingSm
            }

            ScrollView {
                id: playlistScroll
                objectName: "sidebarPlaylistScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                clip: true
                contentWidth: availableWidth
                contentHeight: playlistColumn.implicitHeight
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                Column {
                    id: playlistColumn
                    width: playlistScroll.availableWidth
                    spacing: 4

                    NavigationItem {
                        visible: root.playlists.length === 0
                        width: parent.width
                        height: 44
                        route: "library"
                        icon: "library_music"
                        label: "Tu biblioteca"
                        collapsed: root.sidebarCollapsed
                        active: root.controllerAvailable && navigationController.activePath === route
                        onActivated: if (root.controllerAvailable) navigationController.navigate(route)
                    }

                    Repeater {
                        model: root.playlists

                        delegate: NavigationItem {
                            id: shortcut
                            objectName: "sidebarPlaylistShortcut"
                            required property var modelData
                            width: playlistColumn.width
                            height: 44
                            route: modelData.navigate
                            icon: "playlist_play"
                            label: modelData.title
                            thumbnail: modelData.thumbnail || ""
                            active: root.controllerAvailable && navigationController.activePath === route
                            collapsed: root.sidebarCollapsed
                            onActivated: if (root.controllerAvailable) navigationController.navigate(route)
                            onContextRequested: shortcutMenu.popup()
                            Drag.active: pinDrag.active
                            Drag.dragType: Drag.Automatic
                            Drag.keys: ["doremi-pin"]
                            Drag.mimeData: ({"application/x-doremi-pin": shortcut.route})
                            Drag.supportedActions: Qt.MoveAction
                            DragHandler { id: pinDrag; target: null; enabled: shortcut.modelData.pinned }
                            DropArea {
                                anchors.fill: parent
                                keys: ["doremi-track", "doremi-pin"]
                                onDropped: function(drop) {
                                    if (drop.formats.indexOf("application/x-doremi-pin") >= 0) {
                                        navigationController.move_pin(drop.getDataAsString("application/x-doremi-pin"), shortcut.route)
                                        drop.acceptProposedAction()
                                    } else if (typeof desktopController !== "undefined" && desktopController) {
                                        desktopController.drop_track(drop.getDataAsString("application/x-doremi-track"), shortcut.route)
                                        drop.acceptProposedAction()
                                    }
                                }
                                Rectangle { anchors.fill: parent; visible: parent.containsDrag; color: "transparent"; border.width: 2; border.color: root.colors["accent"]; radius: Theme.radiusMd }
                            }
                            Menu {
                                id: shortcutMenu
                                MenuItem { text: "Abrir"; onTriggered: shortcut.activated() }
                                MenuItem {
                                    text: shortcut.modelData.pinned ? "Desfijar de barra lateral" : "Fijar en barra lateral"
                                    onTriggered: navigationController.toggle_pin(shortcut.route)
                                }
                            }
                        }
                    }
                }
            }
        }

        NavigationItem {
            objectName: "sidebarCollapseButton"
            Layout.fillWidth: true
            route: "navigationController-toggle"
            icon: root.sidebarCollapsed ? "chevron_right" : "chevron_left"
            label: root.sidebarCollapsed ? "Expandir barra lateral" : "Contraer barra lateral"
            collapsed: root.sidebarCollapsed
            onActivated: if (root.controllerAvailable) navigationController.toggleCollapsed()
        }
    }

    component NavigationItem: Item {
        id: item

        property string route: ""
        property string icon: ""
        property string label: ""
        property string thumbnail: ""
        property bool active: false
        property bool collapsed: false
        signal activated()
        signal contextRequested()

        Layout.preferredHeight: 44
        Layout.minimumHeight: 44
        Layout.maximumHeight: 44
        Accessible.role: Accessible.Button
        Accessible.name: label
        Accessible.onPressAction: item.activated()
        activeFocusOnTab: true
        onActiveFocusChanged: {
            if (!activeFocus || parent !== playlistColumn)
                return
            const flickable = playlistScroll.contentItem
            if (y < flickable.contentY)
                flickable.contentY = y
            else if (y + height > flickable.contentY + flickable.height)
                flickable.contentY = y + height - flickable.height
        }
        Keys.onReturnPressed: if (!event.isAutoRepeat) item.activated()
        Keys.onEnterPressed: if (!event.isAutoRepeat) item.activated()
        Keys.onSpacePressed: if (!event.isAutoRepeat) item.activated()
        Keys.onMenuPressed: item.contextRequested()

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusMd
            color: item.active
                   ? Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.14)
                   : (mouse.containsMouse ? root.colors["bg_elevated"] : "transparent")
            border.width: item.activeFocus ? 2 : 0
            border.color: root.colors["accent"]

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: item.collapsed ? 0 : Theme.spacingSm
                anchors.rightMargin: Theme.spacingSm
                spacing: Theme.spacingSm

                Text {
                    visible: item.thumbnail === "" || artwork.status === Image.Error
                    Layout.preferredWidth: item.collapsed ? parent.width : 24
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: item.icon
                    font.family: root.iconFont
                    font.pixelSize: 22
                    color: item.active ? root.colors["accent"] : root.colors["text_secondary"]
                }

                Image {
                    id: artwork
                    visible: item.thumbnail !== "" && status !== Image.Error
                    source: item.thumbnail
                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 30
                    Layout.alignment: Qt.AlignHCenter
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize.width: 60
                    sourceSize.height: 60
                }

                Label {
                    visible: !item.collapsed
                    text: item.label
                    color: item.active ? root.colors["accent"] : root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeLabel
                    font.weight: item.active ? Font.DemiBold : Font.Medium
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: function(mouse) {
                if (mouse.button === Qt.RightButton) { item.contextRequested(); return }
                item.forceActiveFocus()
                item.activated()
            }
        }

        ToolTip.visible: item.collapsed && mouse.containsMouse
        ToolTip.text: item.label
        ToolTip.delay: 450
    }
}
