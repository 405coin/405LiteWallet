import QtQuick
import QtQuick.Controls

import org.electrum 1.0

ElComboBox {
    id: control

    required property QtObject feeslider

    textRole: 'text'
    valueRole: 'value'
    readonly property bool hasOptions: model.length > 1

    model: [
        { text: qsTr('Feerate'), value: FeeSlider.FSMethod.FEERATE }
    ]
    visible: hasOptions
    enabled: hasOptions
    onCurrentValueChanged: {
        if (activeFocus && hasOptions)
            feeslider.method = currentValue
    }
    Component.onCompleted: {
        currentIndex = indexOfValue(feeslider.method)
    }
}
