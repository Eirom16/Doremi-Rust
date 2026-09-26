import QtQuick
import QtQuick.Layouts
import Doremi

Item {
    id: root
    property var toastVm: null
    width: 380
    height: toastCard.implicitHeight
    visible: toastVm && toastVm.visible
    opacity: visible ? 1 : 0

    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    Rectangle {
        id: toastCard
        width: parent.width
        implicitHeight: Math.max(64, messageText.implicitHeight + 24)
        radius: Theme.radiusLg
        color: themeBridge.colors.bg_surface
        border.width: 1
        border.color: toastVm ? toastVm.accentColor : "transparent"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingLg
            anchors.rightMargin: Theme.spacingLg
            anchors.topMargin: Theme.spacingMd
            anchors.bottomMargin: Theme.spacingMd
            spacing: Theme.spacingSm

            Text {
                text: toastVm ? toastVm.iconName : ""
                font.family: "Material Symbols Rounded"
                font.pixelSize: 20
                color: toastVm ? toastVm.accentColor : "transparent"
                Layout.alignment: Qt.AlignTop
            }

            Text {
                id: messageText
                text: toastVm ? toastVm.message : ""
                color: themeBridge.colors.text_primary
                font.family: "Inter"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
            }

            Text {
                visible: toastVm && toastVm.actionText.length > 0
                text: toastVm ? toastVm.actionText : ""
                color: toastVm ? toastVm.accentColor : "transparent"
                font.family: "Inter"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                Layout.alignment: Qt.AlignVCenter

                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -8
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (toastVm) toastVm.triggerAction()
                }
            }
        }
    }
}
