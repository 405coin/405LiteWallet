import QtQuick
import QtQuick.Controls

ComboBox {
    id: cb

    property int implicitChildrenWidth: 64

    
    implicitWidth: Math.ceil(implicitChildrenWidth/32)*32 + 2 * constants.paddingXLarge

    
    contentItem: Label {
        id: contentLabel
        text: cb.currentText
        padding: constants.paddingLarge
        rightPadding: constants.paddingXXLarge
        font.pixelSize: constants.fontSizeMedium
    }

    
    function updateImplicitWidth() {
        for (let i = 0; i < cb.count; i++) {
            var txt = cb.textAt(i)
            var txtwidth = fontMetrics.advanceWidth(txt)
            if (txtwidth > cb.implicitChildrenWidth) {
                cb.implicitChildrenWidth = txtwidth
            }
        }
    }

    FontMetrics {
        id: fontMetrics
        font: contentLabel.font
    }

    Component.onCompleted: updateImplicitWidth()
    onModelChanged: updateImplicitWidth()
}
