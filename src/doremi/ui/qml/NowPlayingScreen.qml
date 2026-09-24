import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (NowPlayingViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    // ── Fondo ambiental: artwork difuminado ──────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: root.colors ? root.colors["bg_base"] : "#11111b"
    }
    Image {
        id: ambientImg
        anchors.fill: parent
        source: vm.artworkUrl
        asynchronous: true
        cache: true
        fillMode: Image.PreserveAspectCrop
        opacity: 0
    }
    FastBlur {
        anchors.fill: parent
        source: ambientImg
        radius: 96
        visible: ambientImg.status === Image.Ready
        opacity: 0.45
    }
    Rectangle {
        anchors.fill: parent
        color: root.colors ? root.colors["bg_base"] : "#11111b"
        opacity: ambientImg.status === Image.Ready ? 0.4 : 0.0
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Barra superior (Minimizar) ────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingLg
            Layout.rightMargin: Theme.spacingLg
            Layout.topMargin: Theme.spacingSm

            Rectangle {
                Layout.preferredWidth: collapseLbl.implicitWidth + Theme.spacingLg * 2
                Layout.preferredHeight: 34
                radius: Theme.radiusSm
                color: collapseMa.containsMouse ? root.colors["bg_elevated"] : "transparent"

                Row {
                    anchors.centerIn: parent
                    spacing: Theme.spacingXxs
                    Text {
                        text: "" // expand_more
                        font.family: root.iconFont
                        font.pixelSize: 16
                        color: root.colors["text_secondary"]
                    }
                    Label {
                        id: collapseLbl
                        text: "Minimizar"
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                    }
                }
                MouseArea {
                    id: collapseMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vm.minimize()
                }
            }
            Rectangle {
                Layout.leftMargin: 60
                Layout.preferredWidth: 212
                Layout.preferredHeight: 38
                radius: Theme.radiusPill
                color: root.colors["bg_elevated"]
                border.width: 1
                border.color: root.colors["border"]

                Row {
                    anchors.fill: parent
                    anchors.margins: 3
                    spacing: 3

                    Repeater {
                        model: [
                            { key: "audio", label: "Audio", icon: "" },
                            { key: "video", label: "Videoclip", icon: "" }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            width: 101
                            height: parent.height
                            radius: Theme.radiusPill
                            color: vm.mediaMode === modelData.key
                                   ? root.accentColor
                                   : "transparent"
                            Row {
                                anchors.centerIn: parent
                                spacing: Theme.spacingXxs
                                Text {
                                    text: modelData.icon
                                    font.family: root.iconFont
                                    font.pixelSize: 16
                                    color: vm.mediaMode === modelData.key
                                           ? root.colors["text_on_accent"]
                                           : root.colors["text_secondary"]
                                }
                                Label {
                                    text: modelData.label
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeCaption
                                    font.weight: Font.DemiBold
                                    color: vm.mediaMode === modelData.key
                                           ? root.colors["text_on_accent"]
                                           : root.colors["text_secondary"]
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: vm.set_media_mode(modelData.key)
                            }
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true }
        }

        // ── Contenido principal ───────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingXl + 8
            Layout.rightMargin: Theme.spacingXl + 8
            Layout.bottomMargin: Theme.spacingLg
            spacing: Theme.spacingXl

            // ── Izquierda: artwork + info + controles ─────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Theme.spacingSm

                Item { Layout.fillHeight: true }

                // Artwork / videoclip sincronizado con el audio principal
                Rectangle {
                    id: mediaFrame
                    objectName: "mediaFrame"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: vm.mediaMode === "video" ? 420 : 280
                    Layout.preferredHeight: vm.mediaMode === "video" ? 236 : 280
                    radius: Theme.radiusLg
                    color: root.colors["bg_elevated"]
                    clip: true

                    Behavior on Layout.preferredWidth {
                        NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
                    }
                    Behavior on Layout.preferredHeight {
                        NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
                    }

                    Item {
                        id: artworkLayer
                        anchors.fill: parent
                        opacity: vm.mediaMode === "audio" ? 1 : 0
                        scale: vm.mediaMode === "audio" ? 1 : 0.985
                        visible: opacity > 0

                        Behavior on opacity {
                            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                        }
                        Behavior on scale {
                            NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
                        }

                        Image {
                            id: artworkImage
                            anchors.fill: parent
                            source: vm.artworkUrl
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            visible: status === Image.Ready
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: artworkImage.status !== Image.Ready
                            text: "" // library_music
                            font.family: root.iconFont
                            font.pixelSize: 100
                            color: root.colors["text_secondary"]
                        }
                    }

                    Item {
                        id: videoLayer
                        anchors.fill: parent
                        opacity: vm.mediaMode === "video" ? 1 : 0
                        scale: vm.mediaMode === "video" ? 1 : 1.015
                        visible: opacity > 0

                        Behavior on opacity {
                            NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
                        }
                        Behavior on scale {
                            NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
                        }

                        BusyIndicator {
                            anchors.centerIn: parent
                            running: vm.videoLoading
                            visible: running
                        }

                        Column {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - Theme.spacingXl, 300)
                            spacing: Theme.spacingSm
                            visible: vm.videoError !== ""
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "" // videocam_off
                                font.family: root.iconFont
                                font.pixelSize: 42
                                color: root.colors["text_secondary"]
                            }
                            Label {
                                width: parent.width
                                text: vm.videoError
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                                color: root.colors["text_secondary"]
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.typeLabel
                            }
                            Button {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: vm.videoRetryText
                                onClicked: vm.request_video_clip()
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: Theme.spacingMd }

                // Título / artista / like
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSm

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            text: vm.trackTitle
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: 20
                            font.weight: Font.Bold
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            id: artistLbl
                            text: vm.artistName
                            color: artistMa.containsMouse ? root.accentColor : root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                            elide: Text.ElideRight
                            Layout.fillWidth: true

                            MouseArea {
                                id: artistMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: vm.press_artist()
                            }
                        }
                    }

                    Rectangle {
                        id: favoriteButton
                        objectName: "nowPlayingFavoriteButton"
                        activeFocusOnTab: enabled && visible
                        Accessible.role: Accessible.Button
                        Accessible.name: vm.favoriteActionText
                        Accessible.checkable: true
                        Accessible.checked: vm.liked
                        Accessible.onPressAction: vm.toggle_like_current()
                        Keys.onReturnPressed: if (!event.isAutoRepeat) vm.toggle_like_current()
                        Keys.onEnterPressed: if (!event.isAutoRepeat) vm.toggle_like_current()
                        Keys.onSpacePressed: if (!event.isAutoRepeat) vm.toggle_like_current()
                        border.width: activeFocus ? 2 : 0
                        border.color: root.accentColor
                        Layout.preferredWidth: 44
                        Layout.preferredHeight: 44
                        radius: 22
                        color: likeMa.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: "" // favorite
                            font.family: root.iconFont
                            font.pixelSize: 24
                            color: vm.liked ? root.colors["like_color"] : root.colors["text_secondary"]
                        }
                        MouseArea {
                            id: likeMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { favoriteButton.forceActiveFocus(); vm.toggle_like_current() }
                        }
                    }
                }

                // Progreso
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSm
                    Label {
                        text: vm.timeCurrent
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.typeCaption
                    }
                    Slider {
                        id: seekSlider
                        Layout.fillWidth: true
                        from: 0; to: 1
                        enabled: vm.videoId !== ""

                        background: Rectangle {
                            x: seekSlider.leftPadding
                            y: seekSlider.topPadding + seekSlider.availableHeight / 2 - 2
                            width: seekSlider.availableWidth
                            height: 4
                            radius: 2
                            color: root.colors["bg_high"]

                            Rectangle {
                                width: (seekSlider.position) * parent.width
                                height: 4
                                radius: 2
                                color: root.accentColor
                            }
                        }
                        handle: Rectangle {
                            x: seekSlider.leftPadding + seekSlider.visualPosition * (seekSlider.availableWidth - width)
                            y: seekSlider.topPadding + seekSlider.availableHeight / 2 - height / 2
                            width: 12; height: 12; radius: 6
                            color: root.accentColor
                        }

                        onMoved: vm.seek(value)
                        // El valor viene de fuera salvo drag del usuario
                        Binding {
                            target: seekSlider
                            property: "value"
                            value: vm.progress
                            when: !seekSlider.pressed
                            restoreMode: Binding.RestoreBindingOrValue
                        }
                    }
                    Label {
                        text: vm.timeTotal
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.typeCaption
                    }
                }

                // Controles
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSm
                    Layout.alignment: Qt.AlignHCenter

                    ControlButton {
                        iconCode: "" // shuffle
                        active: vm.shuffle
                        onClicked: vm.toggle_shuffle()
                    }
                    ControlButton {
                        iconCode: "" // skip_previous
                        big: true
                        onClicked: vm.prev()
                    }

                    Rectangle {
                        Layout.preferredWidth: 60
                        Layout.preferredHeight: 60
                        radius: 30
                        color: playMa.containsMouse ? root.colors["accent_bright"] : root.accentColor

                        Text {
                            anchors.centerIn: parent
                            text: vm.playing ? "" /*pause*/ : "" /*play*/
                            font.family: root.iconFont
                            font.pixelSize: 34
                            color: root.colors["text_on_accent"]
                        }
                        MouseArea {
                            id: playMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: vm.toggle_play()
                        }
                    }

                    ControlButton {
                        iconCode: "" // skip_next
                        big: true
                        onClicked: vm.next()
                    }
                    ControlButton {
                        iconCode: "" // repeat (repeatOne lo sobreescribe)
                        active: vm.repeatMode !== "off"
                        onClicked: vm.cycle_repeat()
                        repeatOne: vm.repeatMode === "one"
                    }

                    // Menú de la pista actual
                    ControlButton {
                        iconCode: "" // more_vert
                        onClicked: currentMenu.popup()
                    }
                }

                Item { Layout.fillHeight: true }
            }

            // ── Derecha: tabs (cola / letra / similares) ──────────────
            Rectangle {
                Layout.preferredWidth: Math.max(420, Math.min(560, root.width * 0.42))
                Layout.fillHeight: true
                color: "transparent"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacingSm

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm

                        Repeater {
                            model: [
                                { "key": "queue", "label": "A continuación" },
                                { "key": "lyrics", "label": "Letra" },
                                { "key": "related", "label": "Similares" }
                            ]
                            delegate: Rectangle {
                                id: tabBtn
                                required property var modelData
                                readonly property bool active: vm.tab === modelData.key

                                Layout.preferredWidth: tabLbl.implicitWidth + Theme.spacingMd * 2
                                Layout.preferredHeight: 34
                                radius: Theme.radiusPill
                                color: active ? root.accentWithAlpha(0.15) : "transparent"
                                border.width: active ? 1 : 0
                                border.color: root.accentColor

                                Label {
                                    id: tabLbl
                                    anchors.centerIn: parent
                                    text: tabBtn.modelData.label
                                    color: tabBtn.active ? root.accentColor : root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: vm.set_tab(tabBtn.modelData.key)
                                }
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }

                    // ── Cola ──────────────────────────────────────────
                    ListView {
                        visible: vm.tab === "queue"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: Theme.spacingXs
                        cacheBuffer: 400
                        model: vm.queueModel

                        Label {
                            visible: vm.queueModel.rowCount() === 0
                            anchors.centerIn: parent
                            text: "La cola está vacía"
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                        }

                        delegate: Rectangle {
                            id: qRow
                            required property int index
                            required property string title
                            required property string artist
                            required property string duration
                            required property string thumbnail
                            required property bool isCurrent

                            width: ListView.view.width
                            height: 64
                            radius: Theme.radiusLg
                            color: isCurrent
                                   ? root.accentWithAlpha(0.13)
                                   : (qMa.containsMouse ? root.colors["bg_high"] : "transparent")
                            border.width: isCurrent ? 1 : 0
                            border.color: root.accentWithAlpha(0.35)

                            MouseArea {
                                id: qMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.LeftButton)
                                        vm.play_queue_index(qRow.index)
                                    else
                                        qMenu.popup()
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Rectangle {
                                    Layout.preferredWidth: 44
                                    Layout.preferredHeight: 44
                                    radius: Theme.radiusSm
                                    color: root.colors["bg_elevated"]
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: qRow.thumbnail
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
                                        text: qRow.title
                                        color: qRow.isCurrent ? root.accentColor : root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeBody
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        text: qRow.artist
                                        color: root.colors["text_secondary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeLabel
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                Label {
                                    text: qRow.duration
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.typeCaption
                                    visible: qRow.duration !== ""
                                }

                                // Reordenar
                                ColumnLayout {
                                    spacing: 0
                                    Text {
                                        text: "" // arrow_upward
                                        font.family: root.iconFont
                                        font.pixelSize: 14
                                        color: upMa.containsMouse ? root.accentColor : root.colors["text_secondary"]
                                        opacity: qRow.index > 0 ? 1.0 : 0.3
                                        Layout.alignment: Qt.AlignHCenter
                                        MouseArea {
                                            id: upMa
                                            anchors.fill: parent
                                            hoverEnabled: qRow.index > 0
                                            cursorShape: qRow.index > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: if (qRow.index > 0) vm.move_queue_item(qRow.index, "up")
                                        }
                                    }
                                    Text {
                                        text: "" // arrow_downward
                                        font.family: root.iconFont
                                        font.pixelSize: 14
                                        color: downMa.containsMouse ? root.accentColor : root.colors["text_secondary"]
                                        opacity: qRow.index < vm.queueModel.rowCount() - 1 ? 1.0 : 0.3
                                        Layout.alignment: Qt.AlignHCenter
                                        MouseArea {
                                            id: downMa
                                            anchors.fill: parent
                                            hoverEnabled: qRow.index < vm.queueModel.rowCount() - 1
                                            cursorShape: qRow.index < vm.queueModel.rowCount() - 1 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: if (qRow.index < vm.queueModel.rowCount() - 1) vm.move_queue_item(qRow.index, "down")
                                        }
                                    }
                                }

                                ContextMenu {
                                    id: qMenu
                                    ContextMenuItem {
                                        text: "Reproducir"
                                        onTriggered: vm.play_queue_index(qRow.index)
                                    }
                                    ContextMenuItem {
                                        text: "Reproducir siguiente"
                                        onTriggered: vm.queue_action(qRow.index, "play_next")
                                    }
                                    ContextMenuItem {
                                        text: "Quitar de la cola"
                                        onTriggered: vm.queue_action(qRow.index, "delete_download")
                                    }
                                }
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    // ── Letra ─────────────────────────────────────────
                    Item {
                        visible: vm.tab === "lyrics"
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        Label {
                            anchors.centerIn: parent
                            visible: !vm.hasLyrics
                            text: "No hay letras disponibles"
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                        }

                        ListView {
                            id: lyricsView
                            anchors.fill: parent
                            visible: vm.hasLyrics
                            clip: true
                            spacing: 0
                            cacheBuffer: 600
                            model: vm.lyrics

                            delegate: Text {
                                id: lyricLine
                                required property int index
                                required property string lineText
                                required property bool active

                                width: lyricsView.width
                                horizontalAlignment: {
                                    if (vm.lyricAlign === "left") return Text.AlignLeft
                                    if (vm.lyricAlign === "right") return Text.AlignRight
                                    return Text.AlignHCenter
                                }
                                wrapMode: Text.WordWrap
                                text: lyricLine.lineText
                                textFormat: Text.PlainText

                                color: active
                                       ? root.colors["text_primary"]
                                       : root.accentWithAlpha(0.55)
                                font.family: Theme.fontFamily
                                font.pixelSize: active ? vm.lyricFontSize : vm.lyricFontSize - 4
                                font.weight: active ? Font.Bold : Font.Medium
                                topPadding: Theme.spacingXs
                                bottomPadding: Theme.spacingXs

                                scale: active && vm.lyricGlow ? 1.03 : 1.0
                                Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                                Behavior on font.pixelSize { NumberAnimation { duration: 200 } }
                            }

                            // Auto-scroll al lyric activo
                            Connections {
                                target: vm
                                function onLyric_index_changed() {
                                    if (vm.lyricAutoScroll && lyricsView.visible) {
                                        var idx = 0
                                        for (var i = 0; i < lyricsView.count; i++) {
                                            if (lyricsView.itemAtIndex(i) && lyricsView.itemAtIndex(i).active) {
                                                idx = i
                                                break
                                            }
                                        }
                                        lyricsView.positionViewAtIndex(idx, ListView.Center)
                                    }
                                }
                            }
                        }
                    }

                    // ── Similares ─────────────────────────────────────
                    ListView {
                        visible: vm.tab === "related"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: Theme.spacingXs
                        cacheBuffer: 400
                        model: vm.related

                        Label {
                            visible: vm.related.rowCount() === 0
                            anchors.centerIn: parent
                            text: "No hay canciones similares"
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                        }

                        delegate: Rectangle {
                            id: rRow
                            required property int index
                            required property string title
                            required property string artist
                            required property string duration
                            required property string thumbnail

                            width: ListView.view.width
                            height: 64
                            radius: Theme.radiusLg
                            color: rMa.containsMouse ? root.colors["bg_high"] : "transparent"

                            MouseArea {
                                id: rMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.LeftButton)
                                        vm.related_action(rRow.index, "play")
                                    else
                                        rMenu.popup()
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Rectangle {
                                    Layout.preferredWidth: 44
                                    Layout.preferredHeight: 44
                                    radius: Theme.radiusSm
                                    color: root.colors["bg_elevated"]
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: rRow.thumbnail
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
                                        text: rRow.title
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeBody
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        text: rRow.artist
                                        color: root.colors["text_secondary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeLabel
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                ContextMenu {
                                    id: rMenu
                                    ContextMenuItem {
                                        text: "Reproducir siguiente"
                                        onTriggered: vm.related_action(rRow.index, "play_next")
                                    }
                                    ContextMenuItem {
                                        text: "Añadir a la cola"
                                        onTriggered: vm.related_action(rRow.index, "add_to_queue")
                                    }
                                    ContextMenuItem {
                                        text: "Me gusta"
                                        onTriggered: vm.related_action(rRow.index, "like")
                                    }
                                    ContextMenuItem {
                                        text: "Añadir a playlist"
                                        onTriggered: vm.related_action(rRow.index, "add_to_playlist")
                                    }
                                    ContextMenuItem {
                                        text: "Descargar"
                                        onTriggered: vm.related_action(rRow.index, "download")
                                    }
                                    ContextMenuItem {
                                        text: "Ir al artista"
                                        onTriggered: vm.related_action(rRow.index, "go_artist")
                                    }
                                }
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }
        }
    }

    // ── Componente: botón de control (shuffle/prev/next/repeat/more) ──
    component ControlButton: Rectangle {
        id: ctrl
        property string iconCode: ""
        property bool active: false
        property bool big: false
        property bool repeatOne: false
        signal clicked()

        Layout.preferredWidth: big ? 48 : 42
        Layout.preferredHeight: big ? 48 : 42
        radius: width / 2
        color: ctrlMa.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"

        Text {
            anchors.centerIn: parent
            text: {
                if (ctrl.repeatOne) return "" // repeat_one
                return ctrl.iconCode
            }
            font.family: root.iconFont
            font.pixelSize: ctrl.big ? 30 : 22
            color: ctrl.active ? root.accentColor : root.colors["text_secondary"]
        }
        MouseArea {
            id: ctrlMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: ctrl.clicked()
        }
    }

    // ── Menú de la pista actual ───────────────────────────────────────
    ContextMenu {
        id: currentMenu
        ContextMenuItem { text: "Reproducir siguiente"; onTriggered: vm.current_track_action("play_next") }
        ContextMenuItem { text: "Añadir a la cola"; onTriggered: vm.current_track_action("add_to_queue") }
        ContextMenuItem { text: "Añadir a playlist"; onTriggered: vm.current_track_action("add_to_playlist") }
        ContextMenuItem { text: "Ir al artista"; onTriggered: vm.current_track_action("go_artist") }
        ContextMenuItem { text: "Ir al álbum"; onTriggered: vm.current_track_action("go_album") }
        ContextMenuItem { text: "Descargar"; onTriggered: vm.current_track_action("download") }
        ContextMenuItem { text: "Ver videoclip"; onTriggered: vm.request_video_clip() }
        ContextMenuItem {
            text: "Detalles y créditos"
            onTriggered: {
                trackDetailsDialog.open()
                vm.request_track_details()
            }
        }
        ContextMenuItem { text: "Copiar enlace"; onTriggered: vm.current_track_action("copy_link") }
    }

    // ── Detalles publicados de la pista ──────────────────────────────
    ModalDialog {
        id: trackDetailsDialog
        dialogTitle: "Detalles y créditos"
        showCancel: false
        confirmText: "Cerrar"

        contentItemData: [
            ColumnLayout {
                width: 372
                spacing: Theme.spacingSm

                Label {
                    Layout.fillWidth: true
                    text: vm.trackTitle
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeBody
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    text: vm.artistName
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeLabel
                    visible: text !== ""
                }
                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: vm.detailsLoading
                    visible: vm.detailsLoading
                }
                Label {
                    Layout.fillWidth: true
                    text: vm.detailsError
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeLabel
                    wrapMode: Text.WordWrap
                    visible: text !== ""
                }
                Repeater {
                    model: [
                        { label: "Artista", value: vm.detailArtist },
                        { label: "Álbum", value: vm.detailAlbum },
                        { label: "Publicado por", value: vm.detailUploader },
                        { label: "Fecha", value: vm.detailReleaseDate },
                        { label: "Licencia", value: vm.detailLicense }
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        visible: modelData.value !== ""
                        spacing: Theme.spacingMd
                        Label {
                            Layout.preferredWidth: 104
                            text: modelData.label
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.value
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        ]
    }

}
