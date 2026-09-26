import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Popup {
    id: root

    property string dialogTitle: ""
    property alias contentItemData: contentContainer.data
    property string confirmText: "Aceptar"
    property string cancelText: "Cancelar"
    property bool showCancel: true
    property bool showConfirm: true

    signal confirmed()
    signal cancelled()

    readonly property var colors: themeBridge.colors

    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    anchors.centerIn: Overlay.overlay

    padding: 0
    background: Rectangle {
        color: "transparent"
    }

    Overlay.modal: Rectangle {
        color: root.colors["bg_overlay"]
        
        Behavior on opacity {
            NumberAnimation { duration: 150 }
        }
    }

    contentItem: Rectangle {
        implicitWidth: 420
        implicitHeight: dialogLayout.implicitHeight + Theme.spacingLg * 2
        radius: Theme.radiusLg
        color: root.colors["bg_surface"]
        border.width: 1
        border.color: root.colors["border"]
        clip: true

        ColumnLayout {
            id: dialogLayout
            anchors.fill: parent
            anchors.margins: Theme.spacingLg
            spacing: Theme.spacingMd

            // Header
            RowLayout {
                Layout.fillWidth: true
                visible: root.dialogTitle !== ""

                Text {
                    Layout.fillWidth: true
                    text: root.dialogTitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeTitle
                    font.weight: Font.Bold
                    color: root.colors["text_primary"]
                    elide: Text.ElideRight
                }

                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: closeMa.containsMouse ? root.colors["bg_high"] : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: ""
                        font.family: "Material Symbols Rounded"
                        font.pixelSize: 18
                        color: root.colors["text_secondary"]
                    }

                    MouseArea {
                        id: closeMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.cancelled()
                            root.close()
                        }
                    }
                }
            }

            // Custom Content Slot
            Item {
                id: contentContainer
                Layout.fillWidth: true
                Layout.preferredHeight: childrenRect.height
            }

            // Action Buttons
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Theme.spacingSm
                spacing: Theme.spacingMd

                Item { Layout.fillWidth: true }

                // Cancel Button
                Rectangle {
                    visible: root.showCancel
                    implicitWidth: cancelLbl.implicitWidth + Theme.spacingLg * 2
                    implicitHeight: 36
                    radius: Theme.radiusMd
                    color: cancelMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                    border.width: 1
                    border.color: root.colors["border"]

                    Text {
                        id: cancelLbl
                        anchors.centerIn: parent
                        text: root.cancelText
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        color: root.colors["text_primary"]
                    }

                    MouseArea {
                        id: cancelMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.cancelled()
                            root.close()
                        }
                    }
                }

                // Confirm Button
                Rectangle {
                    visible: root.showConfirm
                    implicitWidth: confirmLbl.implicitWidth + Theme.spacingLg * 2
                    implicitHeight: 36
                    radius: Theme.radiusMd
                    color: confirmMa.containsMouse ? root.colors["accent_bright"] : root.colors["accent"]

                    Text {
                        id: confirmLbl
                        anchors.centerIn: parent
                        text: root.confirmText
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        font.weight: Font.Bold
                        color: root.colors["bg_base"]
                    }

                    MouseArea {
                        id: confirmMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.confirmed()
                            root.close()
                        }
                    }
                }
            }
        }
    }
}
