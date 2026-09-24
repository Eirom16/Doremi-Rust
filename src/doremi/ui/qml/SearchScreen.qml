import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (SearchViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    readonly property var chipDefs: [
        { "key": "song", "label": "Canciones" },
        { "key": "album", "label": "Álbumes" },
        { "key": "podcast", "label": "Podcasts" },
        { "key": "playlist", "label": "Playlists" }
    ]

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        anchors.topMargin: Theme.spacingMd
        anchors.bottomMargin: themeBridge.miniPlayerVisible ? 112 : Theme.spacingLg
        spacing: Theme.spacingSm

        // ── Query header ──────────────────────────────────────────────
        Label {
            visible: vm.query !== ""
            text: "Resultados para \"" + vm.query + "\""
            color: root.colors["text_primary"]
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeHeading
            font.weight: Font.Bold
            Layout.fillWidth: true
        }

        // ── Category chips ────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSm

            Repeater {
                model: root.chipDefs

                delegate: Rectangle {
                    id: chip
                    required property var modelData
                    readonly property bool active: vm.category === modelData.key

                    Layout.preferredWidth: chipLabel.implicitWidth + Theme.spacingLg * 1.5
                    Layout.preferredHeight: 34
                    radius: Theme.radiusPill
                    color: active ? root.accentColor
                                  : (chipMa.containsMouse ? root.colors["bg_elevated"] : root.colors["bg_surface"])
                    border.width: 1
                    border.color: active ? root.accentColor : root.colors["border"]

                    Label {
                        id: chipLabel
                        anchors.centerIn: parent
                        text: chip.modelData.label
                        color: chip.active ? root.colors["text_on_accent"] : root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }
                    MouseArea {
                        id: chipMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.set_category(chip.modelData.key)
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Carga ─────────────────────────────────────────────────────
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
                text: "Buscando…"
                color: root.colors["text_secondary"]
                font.pixelSize: Theme.typeBody
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        // ── Error ─────────────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !vm.loading && vm.errorText !== ""
            spacing: Theme.spacingMd
            Item { Layout.fillHeight: true }
            Label {
                text: vm.errorText
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                Layout.alignment: Qt.AlignHCenter
            }
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: retryLbl.implicitWidth + Theme.spacingLg * 2
                height: 36
                radius: Theme.radiusPill
                color: retryMa.containsMouse ? root.accentWithAlpha(0.25) : "transparent"
                border.width: 1
                border.color: root.accentColor

                Label {
                    id: retryLbl
                    anchors.centerIn: parent
                    text: "Reintentar"
                    color: root.accentColor
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeLabel
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    id: retryMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vm.retry()
                }
            }
            Item { Layout.fillHeight: true }
        }

        // ── Vacío (sin resultados de la categoría activa) ─────────────
        Label {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !vm.loading && vm.errorText === "" && vm.query !== ""
                     && ((vm.category === "song" && !vm.hasTop)
                         || ((vm.category === "album" || vm.category === "podcast")
                             && vm.albums.rowCount() === 0)
                         || (vm.category === "playlist" && vm.playlists.rowCount() === 0))
            text: "No se encontraron resultados en esta categoría"
            color: root.colors["text_secondary"]
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        // ── Canciones: split (top + featured) y resto ─────────────────
        Flickable {
            id: songsFlick
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !vm.loading && vm.errorText === "" && vm.category === "song" && vm.hasTop
            clip: true
            contentWidth: width
            contentHeight: songsCol.height
            flickableDirection: Flickable.VerticalFlick

            ColumnLayout {
                id: songsCol
                width: songsFlick.width
                spacing: Theme.spacingLg

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingLg

                    // Resultado principal
                    ColumnLayout {
                        Layout.preferredWidth: 320
                        Layout.maximumWidth: 320
                        Layout.alignment: Qt.AlignTop
                        spacing: Theme.spacingSm

                        Label {
                            text: "Resultado principal"
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Bold
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 220
                            radius: Theme.radiusLg
                            border.width: 1
                            border.color: topMa.containsMouse ? root.accentColor : root.colors["border"]
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop {
                                    position: 0.0
                                    color: topMa.containsMouse ? root.colors["bg_elevated"] : root.colors["bg_surface"]
                                }
                                GradientStop {
                                    position: 1.0
                                    color: topMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_elevated"]
                                }
                            }

                            // Fondo clickeable PRIMERO: queda debajo de play/menú.
                            MouseArea {
                                id: topMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: vm.play_top()
                            }

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacingLg
                                spacing: Theme.spacingSm

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacingSm

                                    Rectangle {
                                        Layout.preferredWidth: 92
                                        Layout.preferredHeight: 92
                                        radius: Theme.radiusMd
                                        color: root.colors["bg_surface"]
                                        clip: true

                                        Image {
                                            anchors.fill: parent
                                            source: vm.topThumbnail
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                            cache: true
                                            visible: status === Image.Ready
                                        }
                                        Text {
                                            anchors.centerIn: parent
                                            visible: parent.children[0].status !== Image.Ready
                                            text: "" // library_music
                                            font.family: root.iconFont
                                            font.pixelSize: 40
                                            color: root.colors["text_secondary"]
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    ColumnLayout {
                                        spacing: Theme.spacingXs
                                        Layout.alignment: Qt.AlignVCenter

                                        Rectangle {
                                            width: 44; height: 44; radius: 22
                                            color: topPlayMa.containsMouse ? root.colors["accent_bright"] : root.accentColor
                                            Text {
                                                anchors.centerIn: parent
                                                text: "" // play_arrow
                                                font.family: root.iconFont
                                                font.pixelSize: 24
                                                color: root.colors["text_on_accent"]
                                            }
                                            MouseArea {
                                                id: topPlayMa
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: vm.play_top()
                                            }
                                        }

                                        Rectangle {
                                            width: 44; height: 44; radius: 22
                                            color: topMenuMa.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                                            Text {
                                                anchors.centerIn: parent
                                                text: "" // more_vert
                                                font.family: root.iconFont
                                                font.pixelSize: 24
                                                color: root.colors["text_secondary"]
                                            }
                                            MouseArea {
                                                id: topMenuMa
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: topMenu.popup()
                                            }

                                            ContextMenu {
                                                id: topMenu
                                                ContextMenuItem {
                                                    text: "Reproducir siguiente"
                                                    onTriggered: vm.top_action("play_next")
                                                }
                                                ContextMenuItem {
                                                    text: "Añadir a la cola"
                                                    onTriggered: vm.top_action("add_to_queue")
                                                }
                                                ContextMenuItem {
                                                    text: "Me gusta"
                                                    onTriggered: vm.top_action("like")
                                                }
                                                ContextMenuItem {
                                                    text: "Añadir a playlist"
                                                    onTriggered: vm.top_action("add_to_playlist")
                                                }
                                                ContextMenuItem {
                                                    text: "Descargar"
                                                    onTriggered: vm.top_action("download")
                                                }
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }

                                Label {
                                    text: vm.topTitle
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeHeading
                                    font.weight: Font.ExtraBold
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                RowLayout {
                                    spacing: Theme.spacingSm
                                    Rectangle {
                                        width: typeLbl.implicitWidth + Theme.spacingSm * 2
                                        height: 18
                                        radius: Theme.radiusSm / 2
                                        color: root.accentColor
                                        Label {
                                            id: typeLbl
                                            anchors.centerIn: parent
                                            text: vm.topType.toUpperCase()
                                            color: root.colors["text_on_accent"]
                                            font.family: Theme.fontFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                        }
                                    }
                                    Label {
                                        text: vm.topArtist
                                        color: root.colors["text_secondary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeLabel
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                    }

                    // Canciones principales (4 destacadas)
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: Theme.spacingXs
                        visible: vm.featured.rowCount() > 0

                        Label {
                            text: "Canciones principales"
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Bold
                            Layout.bottomMargin: Theme.spacingXs
                        }

                        Repeater {
                            model: vm.featured
                            delegate: songRowComponent
                            // ancho gestionado por el ColumnLayout padre
                        }
                    }
                }

                // Más canciones
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingXs
                    visible: vm.rest.rowCount() > 0

                    Label {
                        text: "Más canciones"
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        font.weight: Font.Bold
                        Layout.bottomMargin: Theme.spacingXs
                    }

                    Repeater {
                        model: vm.rest
                        delegate: restSongRowComponent
                    }
                }
            }
        }

        // ── Grids (álbumes / playlists) ───────────────────────────────
        GridView {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !vm.loading && vm.errorText === "" && vm.category !== "song"
                     && (((vm.category === "album" || vm.category === "podcast")
                          && vm.albums.rowCount() > 0)
                         || (vm.category === "playlist" && vm.playlists.rowCount() > 0))
            clip: true
            cacheBuffer: 400

            readonly property int cols: Math.max(2, Math.floor(width / 190))
            cellWidth: width / cols
            cellHeight: 216

            model: (vm.category === "album" || vm.category === "podcast")
                   ? vm.albums : vm.playlists

            delegate: Item {
                id: gridCell
                width: grid.cellWidth
                height: grid.cellHeight

                required property int index
                required property string title
                required property string thumbnail
                required property string navigate
                // ambos modelos exponen 'subtitle'; isDownloaded solo playlists
                required property string subtitle
                property bool isDl: (typeof isDownloaded !== "undefined") ? isDownloaded : false

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingXs
                    radius: Theme.radiusLg
                    color: gridMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                    border.width: 1
                    border.color: gridMa.containsMouse ? root.colors["border_focus"] : root.colors["border"]

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSm
                        spacing: Theme.spacingXs

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: Theme.radiusMd
                            color: root.colors["bg_elevated"]
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: gridCell.thumbnail
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                visible: status === Image.Ready
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: parent.children[0].status !== Image.Ready
                                text: vm.category === "podcast" ? ""
                                      : (vm.category === "album" ? "" : "")
                                font.family: root.iconFont
                                font.pixelSize: 36
                                color: root.colors["text_secondary"]
                            }

                            // Badge descargada
                            Rectangle {
                                visible: gridCell.isDl
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: Theme.spacingXs
                                width: dlBadge.implicitWidth + Theme.spacingSm
                                height: 22
                                radius: Theme.radiusPill
                                color: root.colors ? Qt.rgba(0, 0, 0, 0.7) : "#cc000000"

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 2
                                    Text {
                                        text: "" // download_done
                                        font.family: root.iconFont
                                        font.pixelSize: 13
                                        color: root.accentColor
                                    }
                                    Label {
                                        id: dlBadge
                                        text: "Descargada"
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeCaption
                                    }
                                }
                            }
                        }

                        Label {
                            text: gridCell.title
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Label {
                            visible: gridCell.subtitle !== ""
                            text: gridCell.subtitle
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeCaption
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    MouseArea {
                        id: gridMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (gridCell.navigate)
                                vm.navigate(gridCell.navigate)
                        }
                    }
                }
            }

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }
    }

    // ── Fila de canción reutilizable (featured usa modelo vm.featured) ─
    Component {
        id: songRowComponent

        Rectangle {
            id: songRow
            required property int index
            required property string title
            required property string artist
            required property string duration
            required property string thumbnail

            Layout.fillWidth: true
            Layout.preferredHeight: 64
            radius: Theme.radiusLg
            color: songMa.containsMouse ? root.colors["bg_high"] : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingSm
                anchors.rightMargin: Theme.spacingSm
                spacing: Theme.spacingMd

                Rectangle {
                    Layout.preferredWidth: 48
                    Layout.preferredHeight: 48
                    radius: Theme.radiusSm
                    color: root.colors["bg_elevated"]
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: songRow.thumbnail
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        visible: status === Image.Ready
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: parent.children[0].status !== Image.Ready
                        text: "" // library_music
                        font.family: root.iconFont
                        font.pixelSize: 20
                        color: root.colors["text_secondary"]
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Label {
                        text: songRow.title
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeBody
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Label {
                        text: songRow.artist
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                Label {
                    text: songRow.duration
                    color: root.colors["text_secondary"]
                    font.pixelSize: Theme.typeCaption
                    font.family: Theme.fontMono
                    visible: songRow.duration !== ""
                }

                ContextMenu {
                    id: songMenu
                    ContextMenuItem {
                        text: "Reproducir siguiente"
                        onTriggered: vm.featured_action(songRow.index, "play_next")
                    }
                    ContextMenuItem {
                        text: "Añadir a la cola"
                        onTriggered: vm.featured_action(songRow.index, "add_to_queue")
                    }
                    ContextMenuItem {
                        text: "Me gusta"
                        onTriggered: vm.featured_action(songRow.index, "like")
                    }
                    ContextMenuItem {
                        text: "Añadir a playlist"
                        onTriggered: vm.featured_action(songRow.index, "add_to_playlist")
                    }
                    ContextMenuItem {
                        text: "Descargar"
                        onTriggered: vm.featured_action(songRow.index, "download")
                    }
                }
            }

            MouseArea {
                id: songMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (mouse) => {
                    if (mouse.button === Qt.LeftButton)
                        vm.play_featured(songRow.index)
                    else
                        songMenu.popup()
                }
            }
        }
    }

    // ── Variante para el resto (modelo vm.rest) ───────────────────────
    Component {
        id: restSongRowComponent

        Rectangle {
            id: restRow
            required property int index
            required property string title
            required property string artist
            required property string duration
            required property string thumbnail

            Layout.fillWidth: true
            Layout.preferredHeight: 64
            radius: Theme.radiusLg
            color: restMa.containsMouse ? root.colors["bg_high"] : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingSm
                anchors.rightMargin: Theme.spacingSm
                spacing: Theme.spacingMd

                Rectangle {
                    Layout.preferredWidth: 48
                    Layout.preferredHeight: 48
                    radius: Theme.radiusSm
                    color: root.colors["bg_elevated"]
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: restRow.thumbnail
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        visible: status === Image.Ready
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: parent.children[0].status !== Image.Ready
                        text: "" // library_music
                        font.family: root.iconFont
                        font.pixelSize: 20
                        color: root.colors["text_secondary"]
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Label {
                        text: restRow.title
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeBody
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Label {
                        text: restRow.artist
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                Label {
                    text: restRow.duration
                    color: root.colors["text_secondary"]
                    font.pixelSize: Theme.typeCaption
                    font.family: Theme.fontMono
                    visible: restRow.duration !== ""
                }

                ContextMenu {
                    id: restMenu
                    ContextMenuItem {
                        text: "Reproducir siguiente"
                        onTriggered: vm.rest_action(restRow.index, "play_next")
                    }
                    ContextMenuItem {
                        text: "Añadir a la cola"
                        onTriggered: vm.rest_action(restRow.index, "add_to_queue")
                    }
                    ContextMenuItem {
                        text: "Me gusta"
                        onTriggered: vm.rest_action(restRow.index, "like")
                    }
                    ContextMenuItem {
                        text: "Añadir a playlist"
                        onTriggered: vm.rest_action(restRow.index, "add_to_playlist")
                    }
                    ContextMenuItem {
                        text: "Descargar"
                        onTriggered: vm.rest_action(restRow.index, "download")
                    }
                }
            }

            MouseArea {
                id: restMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (mouse) => {
                    if (mouse.button === Qt.LeftButton)
                        vm.play_rest(restRow.index)
                    else
                        restMenu.popup()
                }
            }
        }
    }
}
