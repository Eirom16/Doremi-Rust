import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import Doremi 1.0

Item {
    id: root

    // Compatibilidad con la isla actual; MainShell inyectará esta propiedad.
    property var headerController: null
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property int searchWidth: Math.min(600, Math.max(300, width - 200))
    property int searchX: Math.round((width - searchWidth) / 2)

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
        border.width: 0

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: root.colors["border"]
        }
    }

    Rectangle {
        id: searchBox
        x: root.searchX
        anchors.verticalCenter: parent.verticalCenter
        width: root.searchWidth
        height: 44
        radius: Theme.radiusPill
        color: root.colors["bg_surface"]
        border.width: searchInput.activeFocus ? 2 : 1
        border.color: searchInput.activeFocus ? root.colors["accent"] : root.colors["border"]

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingMd
            anchors.rightMargin: Theme.spacingSm
            spacing: Theme.spacingSm

            Text {
                text: "\ue8b6"
                font.family: root.iconFont
                font.pixelSize: 20
                color: root.colors["accent"]
            }

            TextField {
                id: searchInput
                objectName: "searchInput"
                Layout.fillWidth: true
                background: Item {}
                color: root.colors["text_primary"]
                placeholderTextColor: root.colors["text_secondary"]
                placeholderText: "¿Qué quieres escuchar hoy?"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeBody
                selectByMouse: true
                onTextEdited: if (headerController) headerController.setQuery(text)
                onAccepted: if (headerController) headerController.submit()
            }

            Item {
                visible: searchInput.text.length > 0
                width: 32
                height: 32

                Text {
                    anchors.centerIn: parent
                    text: "\ue5cd"
                    font.family: root.iconFont
                    font.pixelSize: 19
                    color: clearMouse.containsMouse ? root.colors["text_primary"] : root.colors["text_secondary"]
                }
                MouseArea {
                    id: clearMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (headerController) headerController.clearQuery()
                }
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingLg
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacingXs

        Item {
            width: 38
            height: 38
            Accessible.role: Accessible.Button
            Accessible.name: "Notificaciones"
            Accessible.onPressAction: if (headerController) headerController.requestNotifications()

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: notificationsMouse.containsMouse ? root.colors["bg_elevated"] : "transparent"
            }
            Text {
                anchors.centerIn: parent
                text: headerController && headerController.notificationsOpen ? "\ue5cd" : "\ue7f4"
                font.family: root.iconFont
                font.pixelSize: 21
                color: root.colors["text_primary"]
            }
            Rectangle {
                visible: headerController && headerController.hasUnread
                width: 8
                height: 8
                radius: 4
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 6
                anchors.rightMargin: 5
                color: root.colors["accent"]
            }
            MouseArea {
                id: notificationsMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (headerController) headerController.requestNotifications()
            }
            ToolTip.visible: notificationsMouse.containsMouse
            ToolTip.text: "Notificaciones"
            ToolTip.delay: 450
        }

        Item {
            width: 38
            height: 38
            Accessible.role: Accessible.Button
            Accessible.name: headerController ? headerController.profileLabel : "Iniciar sesión"
            Accessible.onPressAction: if (headerController) headerController.requestProfile()

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: profileMouse.containsMouse ? root.colors["bg_elevated"] : "transparent"
            }
            Image {
                anchors.centerIn: parent
                width: 28
                height: 28
                source: headerController ? headerController.avatarUrl : ""
                visible: source != ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                layer.enabled: true
                layer.effect: OpacityMask {
                    maskSource: Rectangle { width: 28; height: 28; radius: 14 }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: !(headerController && headerController.avatarUrl.length > 0)
                text: "\ue7fd"
                font.family: root.iconFont
                font.pixelSize: 22
                color: root.colors["text_primary"]
            }
            MouseArea {
                id: profileMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (headerController) headerController.requestProfile()
            }
            ToolTip.visible: profileMouse.containsMouse
            ToolTip.text: headerController ? headerController.profileLabel : "Iniciar sesión"
            ToolTip.delay: 450
        }
    }

    Connections {
        target: headerController
        function onFocusRequestedChanged() {
            searchInput.forceActiveFocus()
            searchInput.selectAll()
        }
        function onQueryChanged() {
            if (headerController && searchInput.text !== headerController.query)
                searchInput.text = headerController.query
        }
    }
}
