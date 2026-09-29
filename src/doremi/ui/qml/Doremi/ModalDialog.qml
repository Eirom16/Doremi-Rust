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
    onOpened: if (showConfirm) confirmButton.forceActiveFocus()

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
                    id: closeButton
                    objectName: "dialogCloseButton"
                    width: 28
                    height: 28
                    radius: 14
                    color: closeMa.containsMouse ? root.colors["bg_high"] : "transparent"
                    border.width: activeFocus ? 2 : 0
                    border.color: root.colors["accent"]
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: "Cerrar diálogo"
                    Accessible.onPressAction: {
                        root.cancelled()
                        root.close()
                    }
                    Keys.onReturnPressed: function(event) { if (!event.isAutoRepeat) { root.cancelled(); root.close() } }
                    Keys.onEnterPressed: function(event) { if (!event.isAutoRepeat) { root.cancelled(); root.close() } }
                    Keys.onSpacePressed: function(event) { if (!event.isAutoRepeat) { root.cancelled(); root.close() } }

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
                    ToolTip.visible: closeMa.containsMouse
                    ToolTip.text: "Cerrar"
                    ToolTip.delay: 450
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
                    id: cancelButton
                    objectName: "dialogCancelButton"
                    visible: root.showCancel
                    implicitWidth: cancelLbl.implicitWidth + Theme.spacingLg * 2
                    implicitHeight: 36
                    radius: Theme.radiusMd
                    color: cancelMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                    border.width: 1
                    border.color: root.colors["border"]
                    activeFocusOnTab: visible
                    Accessible.role: Accessible.Button
                    Accessible.name: root.cancelText
                    Accessible.onPressAction: {
                        root.cancelled()
                        root.close()
                    }
                    Keys.onReturnPressed: function(event) { if (!event.isAutoRepeat) { root.cancelled(); root.close() } }
                    Keys.onEnterPressed: function(event) { if (!event.isAutoRepeat) { root.cancelled(); root.close() } }
                    Keys.onSpacePressed: function(event) { if (!event.isAutoRepeat) { root.cancelled(); root.close() } }

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
                    id: confirmButton
                    objectName: "dialogConfirmButton"
                    visible: root.showConfirm
                    implicitWidth: confirmLbl.implicitWidth + Theme.spacingLg * 2
                    implicitHeight: 36
                    radius: Theme.radiusMd
                    color: confirmMa.containsMouse ? Qt.darker(root.colors["accent"], 1.2) : root.colors["accent"]
                    border.width: activeFocus ? 2 : 0
                    border.color: activeFocus ? root.colors["text_primary"] : "transparent"
                    activeFocusOnTab: visible
                    Accessible.role: Accessible.Button
                    Accessible.name: root.confirmText
                    Accessible.onPressAction: {
                        root.confirmed()
                        root.close()
                    }
                    Keys.onReturnPressed: function(event) { if (!event.isAutoRepeat) { root.confirmed(); root.close() } }
                    Keys.onEnterPressed: function(event) { if (!event.isAutoRepeat) { root.confirmed(); root.close() } }
                    Keys.onSpacePressed: function(event) { if (!event.isAutoRepeat) { root.confirmed(); root.close() } }

                    Text {
                        id: confirmLbl
                        anchors.centerIn: parent
                        text: root.confirmText
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        font.weight: Font.Bold
                        color: root.colors["text_on_accent"]
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
