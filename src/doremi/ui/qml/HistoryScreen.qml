import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (HistoryViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors

    // Medidor FPS del piloto (activable con DoremiFpsOverlay desde Python).
    property bool showFps: false
    property int _fpsFrames: 0
    property int fps: 0

    FrameAnimation {
        running: root.showFps
        onTriggered: root._fpsFrames++
    }
    Timer {
        interval: 1000
        running: root.showFps
        repeat: true
        onTriggered: { root.fps = root._fpsFrames; root._fpsFrames = 0 }
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLg
        anchors.bottomMargin: themeBridge.miniPlayerVisible ? 112 : Theme.spacingLg
        spacing: Theme.spacingSm

        // ── Header ────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Label {
                text: "Historial"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeDisplay * 0.75
                font.weight: Font.DemiBold
                font.letterSpacing: -0.3
                Layout.fillWidth: true
            }

            // Botón "Limpiar historial" — ghost pill (spec: Radius.PILL solo acciones)
            Rectangle {
                id: clearBtn
                property bool hovered: false
                width: clearLabel.implicitWidth + Theme.spacingLg * 2
                height: 40
                radius: Theme.radiusPill
                color: hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                border.width: 1
                border.color: root.colors["error"]

                Label {
                    id: clearLabel
                    anchors.centerIn: parent
                    text: "Limpiar historial"
                    color: root.colors["error"]
                    font.pixelSize: Theme.typeLabel
                    font.family: Theme.fontFamily
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: clearBtn.hovered = true
                    onExited: clearBtn.hovered = false
                    onClicked: confirmClear.open()
                }
            }
        }

        // ── Lista ─────────────────────────────────────────────────────
        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !vm.loading && !vm.empty
            model: vm.model
            clip: true
            spacing: Theme.spacingXs
            cacheBuffer: 600 // pre-render extra para scroll suave

            delegate: Rectangle {
                id: row
                width: listView.width
                height: 64
                radius: Theme.radiusLg
                color: rowMa.containsMouse ? root.colors["bg_high"] : "transparent"

                required property int index
                required property string title
                required property string artist
                required property string duration
                required property string thumbnail
                required property string videoId

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingSm
                    anchors.rightMargin: Theme.spacingSm
                    spacing: Theme.spacingMd

                    // Artwork 48px — radio sm (spec: thumbnails de lista)
                    Rectangle {
                        Layout.preferredWidth: 48
                        Layout.preferredHeight: 48
                        radius: Theme.radiusSm
                        color: root.colors["bg_elevated"]
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: row.thumbnail
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Label {
                            text: row.title
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Label {
                            text: row.artist
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    Label {
                        text: row.duration
                        color: root.colors["text_secondary"]
                        font.pixelSize: Theme.typeLabel
                        font.family: Theme.fontMono
                    }
                }

                MouseArea {
                    id: rowMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: (mouse) => {
                        if (mouse.button === Qt.LeftButton)
                            vm.play_at(row.index)
                        else
                            rowMenu.popup()
                    }

                    ContextMenu {
                        id: rowMenu
                        ContextMenuItem {
                            text: "Reproducir"
                            onTriggered: vm.play_at(row.index)
                        }
                        ContextMenuItem {
                            text: "Reproducir siguiente"
                            onTriggered: vm.action_at(row.index, "play_next")
                        }
                        ContextMenuItem {
                            text: "Añadir a la cola"
                            onTriggered: vm.action_at(row.index, "add_to_queue")
                        }
                        ContextMenuItem {
                            text: "Me gusta"
                            onTriggered: vm.action_at(row.index, "like")
                        }
                        ContextMenuItem {
                            text: "Añadir a playlist"
                            onTriggered: vm.action_at(row.index, "add_to_playlist")
                        }
                        ContextMenuItem {
                            text: "Descargar"
                            onTriggered: vm.action_at(row.index, "download")
                        }
                        ContextMenuItem {
                            text: "Ir al artista"
                            onTriggered: vm.action_at(row.index, "go_artist")
                        }
                    }
                }
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }
        }

        // ── Estado de carga ───────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: vm.loading
            spacing: Theme.spacingMd

            Item { Layout.fillHeight: true }
            BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                running: vm.loading
            }
            Label {
                text: "Cargando historial…"
                color: root.colors["text_secondary"]
                font.pixelSize: Theme.typeBody
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        // ── Estado vacío ──────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: vm.empty && !vm.loading
            spacing: Theme.spacingMd

            Item { Layout.fillHeight: true }
            Label {
                text: "Tu historial está vacío"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                font.weight: Font.DemiBold
                Layout.alignment: Qt.AlignHCenter
            }
            Label {
                text: "Las canciones que reproduzcas aparecerán aquí"
                color: root.colors["text_secondary"]
                font.pixelSize: Theme.typeBody
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }
    }

    // ── Overlay FPS (piloto de medición) ──────────────────────────────
    Rectangle {
        visible: root.showFps
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Theme.spacingSm
        width: fpsLabel.implicitWidth + Theme.spacingMd
        height: fpsLabel.implicitHeight + Theme.spacingXs
        color: root.colors ? root.colors["bg_base"] : "#11111b"
        opacity: 0.8
        radius: Theme.radiusSm
        z: 100

        Label {
            id: fpsLabel
            anchors.centerIn: parent
            text: root.fps + " fps"
            color: root.fps >= 55 ? "#34D399" : (root.fps >= 30 ? "#FBBF24" : "#F87171")
            font.pixelSize: Theme.typeLabel
            font.family: Theme.fontMono
        }
    }

    // ── Diálogo de confirmación para limpiar ─────────────────────────
    Dialog {
        id: confirmClear
        title: "Limpiar historial"
        modal: true
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Yes | Dialog.Cancel

        Label {
            text: "¿Eliminar todo el historial local de reproducción?"
            color: root.colors["text_primary"]
        }

        onAccepted: vm.clear()
    }
}
