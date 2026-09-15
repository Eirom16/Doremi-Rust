import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import Doremi 1.0

Item {
    id: root
    readonly property var colors: themeBridge.colors

    // Iconos Material Symbols (familia ya registrada por load_fonts())
    readonly property string iconFont: "Material Symbols Rounded"

    // Cápsula flotante — fondo translúcido como capa separada (la opacidad
    // NO debe heredarse al contenido: paridad con la versión widgets).
    Item {
        id: capsule
        anchors {
            fill: parent
            leftMargin: Theme.spacingSm
            rightMargin: Theme.spacingSm
            topMargin: Theme.spacingXxs
            bottomMargin: Theme.spacingXxs
        }

        Rectangle {
            anchors.fill: parent
            radius: 16
            color: root.colors["bg_surface"]
            opacity: 0.94
            border.width: 1
            border.color: root.colors["border_focus"]
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingSm
            anchors.rightMargin: Theme.spacingMd
            spacing: 14

            // ── Artwork 60×60 ──────────────────────────────────────────
            Item {
                Layout.preferredWidth: 60
                Layout.preferredHeight: 60
                Layout.alignment: Qt.AlignVCenter

                Rectangle {
                    id: artworkBox
                    anchors.fill: parent
                    radius: Theme.radiusMd
                    color: root.colors["bg_elevated"]
                    layer.enabled: true
                    layer.effect: OpacityMask {
                        maskSource: Rectangle {
                            width: artworkBox.width
                            height: artworkBox.height
                            radius: Theme.radiusMd
                        }
                    }

                    Image {
                        id: artworkImg
                        anchors.fill: parent
                        source: vm.artwork
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        visible: vm.artwork !== ""

                        Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
                    }

                    // Placeholder: icono de música
                    Text {
                        anchors.centerIn: parent
                        visible: vm.artwork === ""
                        text: "\ue405" // library_music aprox en Material Symbols
                        font.family: root.iconFont
                        font.pixelSize: 28
                        color: root.colors["text_secondary"]
                    }

                    // Overlay de carga
                    Rectangle {
                        anchors.fill: parent
                        visible: vm.loading
                        color: Qt.rgba(0, 0, 0, 0.55)
                        BusyIndicator {
                            anchors.centerIn: parent
                            running: vm.loading
                            implicitWidth: 32
                            implicitHeight: 32
                        }
                    }
                }
            }

            // ── Título + artista ───────────────────────────────────────
            ColumnLayout {
                Layout.preferredWidth: 220
                Layout.maximumWidth: 220
                Layout.alignment: Qt.AlignVCenter
                spacing: 2

                Label {
                    text: vm.title
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    font.letterSpacing: -0.2
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Label {
                    text: vm.artist
                    color: artistMa.containsMouse ? root.colors["accent"] : root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeCaption
                    elide: Text.ElideRight
                    Layout.fillWidth: true

                    MouseArea {
                        id: artistMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.emit_artist_clicked(vm.artist)
                    }
                }
            }

            // ── Progreso (tiempo + barra + tiempo) ─────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingXs + 2

                Label {
                    text: vm.positionText
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.typeCaption
                    horizontalAlignment: Text.AlignRight
                    Layout.preferredWidth: 36
                }

                // Barra animada con seek
                Item {
                    id: progressBar
                    Layout.fillWidth: true
                    Layout.preferredHeight: 24
                    Layout.alignment: Qt.AlignVCenter

                    Rectangle {
                        id: track
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width
                        height: progressMa.containsMouse ? 6 : 4
                        radius: height / 2
                        color: root.colors["bg_high"]

                        Behavior on height { NumberAnimation { duration: 120 } }

                        Rectangle {
                            width: parent.width * Math.max(0, Math.min(1, vm.progress))
                            height: parent.height
                            radius: parent.radius
                            color: progressMa.pressed ? root.colors["accent_bright"] : root.colors["accent"]

                            Behavior on width {
                                // No animar en drag para que el thumb siga al dedo
                                enabled: !progressMa.pressed
                                SmoothedAnimation { velocity: 400 }
                            }
                        }
                    }

                    MouseArea {
                        id: progressMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onPressed: (mouse) => vm.emit_seek(mouse.x / width)
                        onPositionChanged: (mouse) => {
                            if (pressed) vm.emit_seek(mouse.x / width)
                        }
                    }
                }

                Label {
                    text: vm.durationText
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.typeCaption
                    Layout.preferredWidth: 36
                }
            }

            // ── Controles ──────────────────────────────────────────────
            RowLayout {
                spacing: Theme.spacingXxs

                // Prev
                Rectangle {
                    width: 42; height: 42; radius: 21
                    color: prevMa.containsMouse ? root.colors["bg_high"] : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: "\ue045" // skip_previous
                        font.family: root.iconFont
                        font.pixelSize: 28
                        color: root.colors["text_primary"]
                    }
                    MouseArea {
                        id: prevMa; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.emit_prev()
                    }
                }

                // Play/Pause — acento, círculo completo (acción primaria)
                Rectangle {
                    width: 52; height: 52; radius: 26
                    color: playMa.containsMouse ? root.colors["accent_bright"] : root.colors["accent"]
                    scale: playMa.pressed ? 0.95 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100 } }

                    Text {
                        anchors.centerIn: parent
                        anchors.horizontalCenterOffset: vm.playing ? 0 : 2
                        text: vm.playing ? "\ue034" : "\ue037" // pause / play_arrow
                        font.family: root.iconFont
                        font.pixelSize: 36
                        color: root.colors["text_on_accent"]
                    }
                    MouseArea {
                        id: playMa; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.emit_play_pause()
                    }
                }

                // Next
                Rectangle {
                    width: 42; height: 42; radius: 21
                    color: nextMa.containsMouse ? root.colors["bg_high"] : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: "\ue044" // skip_next
                        font.family: root.iconFont
                        font.pixelSize: 28
                        color: root.colors["text_primary"]
                    }
                    MouseArea {
                        id: nextMa; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.emit_next()
                    }
                }

                // Expand
                Rectangle {
                    width: 38; height: 38; radius: 19
                    color: expandMa.containsMouse ? root.colors["bg_high"] : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: vm.expandLess ? "\ue5ce" : "\ue5cf" // expand_less / expand_more
                        font.family: root.iconFont
                        font.pixelSize: 24
                        color: root.colors["text_secondary"]
                    }
                    MouseArea {
                        id: expandMa; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.emit_expand()
                    }
                }
            }
        }
    }
}
