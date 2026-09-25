import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // Compatibilidad con la isla actual; MainShell inyectará esta propiedad.
    property var navigationController: null
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
                visible: navigationController.collapsed
                width: 44
                height: 44
                anchors.centerIn: parent
                source: navigationController.appIconSource
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }

            Label {
                visible: !navigationController.collapsed
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
            visible: !navigationController.collapsed
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
            active: navigationController.activeRoute === route
            collapsed: navigationController.collapsed
            onActivated: navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "library"
            icon: "library_music"
            label: "Biblioteca"
            active: navigationController.activeRoute === route
            collapsed: navigationController.collapsed
            onActivated: navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "history"
            icon: "history"
            label: "Historial"
            active: navigationController.activeRoute === route
            collapsed: navigationController.collapsed
            onActivated: navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "stats"
            icon: "bar_chart"
            label: "Estadísticas"
            active: navigationController.activeRoute === route
            collapsed: navigationController.collapsed
            onActivated: navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "downloads"
            icon: "download"
            label: "Descargas"
            active: navigationController.activeRoute === route
            collapsed: navigationController.collapsed
            onActivated: navigationController.navigate(route)
        }

        NavigationItem {
            Layout.fillWidth: true
            route: "settings"
            icon: "settings"
            label: "Ajustes"
            active: navigationController.activeRoute === route
            collapsed: navigationController.collapsed
            onActivated: navigationController.navigate(route)
        }

        ColumnLayout {
            visible: navigationController.playlists.length > 0
            Layout.fillWidth: true
            Layout.topMargin: Theme.spacingSm
            spacing: 4

            Label {
                visible: !navigationController.collapsed
                text: "Tus playlists"
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeCaption
                font.weight: Font.Medium
                Layout.leftMargin: Theme.spacingSm
            }

            Repeater {
                model: navigationController.playlists

                delegate: NavigationItem {
                    required property var modelData
                    Layout.fillWidth: true
                    route: modelData.navigate
                    icon: "playlist_play"
                    label: modelData.title
                    active: navigationController.activeRoute === route
                            || (navigationController.activeRoute === "playlist"
                                && route.indexOf("playlist?") === 0)
                    collapsed: navigationController.collapsed
                    onActivated: navigationController.navigate(route)
                }
            }
        }

        Item { Layout.fillHeight: true }

        NavigationItem {
            Layout.fillWidth: true
            route: "navigationController-toggle"
            icon: navigationController.collapsed ? "chevron_right" : "chevron_left"
            label: navigationController.collapsed ? "Expandir barra lateral" : "Contraer barra lateral"
            collapsed: navigationController.collapsed
            onActivated: navigationController.toggleCollapsed()
        }
    }

    component NavigationItem: Item {
        id: item

        property string route: ""
        property string icon: ""
        property string label: ""
        property bool active: false
        property bool collapsed: false
        signal activated()

        Layout.preferredHeight: 44
        Accessible.role: Accessible.Button
        Accessible.name: label
        Accessible.onPressAction: item.activated()
        activeFocusOnTab: true
        Keys.onReturnPressed: if (!event.isAutoRepeat) item.activated()
        Keys.onEnterPressed: if (!event.isAutoRepeat) item.activated()
        Keys.onSpacePressed: if (!event.isAutoRepeat) item.activated()

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
                    Layout.preferredWidth: item.collapsed ? parent.width : 24
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: item.icon
                    font.family: root.iconFont
                    font.pixelSize: 22
                    color: item.active ? root.colors["accent"] : root.colors["text_secondary"]
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
            onClicked: {
                item.forceActiveFocus()
                item.activated()
            }
        }

        ToolTip.visible: item.collapsed && mouse.containsMouse
        ToolTip.text: item.label
        ToolTip.delay: 450
    }
}
