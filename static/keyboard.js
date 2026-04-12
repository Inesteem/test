/**
 * On-screen keyboard for quiz team client (kiosk mode).
 * Based on simple-keyboard v3.8.125.
 */
(function() {
    let activeInput = null;
    let layoutChanging = false;
    let ignoreNextDismiss = false;
    const kbdWrap = document.getElementById('keyboard');
    if (!kbdWrap) return;

    const kbd = new SimpleKeyboard.default({
        onChange: value => {
            if (activeInput) {
                activeInput.value = value;
                activeInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        },
        onKeyPress: button => {
            if (button === '{shift}' || button === '{lock}') {
                const isShift = kbd.options.layoutName !== 'shift';
                switchLayout(isShift ? 'shift' : 'default');
            } else if (kbd.options.layoutName === 'shift' && button !== '{backspace}' && !button.startsWith('{')) {
                switchLayout('default');
            } else if (button === '{numbers}') {
                switchLayout('numbers');
            } else if (button === '{abc}') {
                switchLayout('default');
            } else if (button === '{special}') {
                switchLayout('special');
            } else if (kbd.options.layoutName === 'special' && !button.startsWith('{')) {
                switchLayout('default');
            } else if (button === '{done}') {
                hideKeyboard();
            }
        },
        layout: {
            'default': [
                'q w e r t y u i o p',
                'a s d f g h j k l',
                '{shift} z x c v b n m {backspace}',
                '{numbers} {special} {space} . {done}'
            ],
            'shift': [
                'Q W E R T Y U I O P',
                'A S D F G H J K L',
                '{lock} Z X C V B N M {backspace}',
                '{numbers} {special} {space} . {done}'
            ],
            'numbers': [
                '1 2 3 4 5 6 7 8 9 0',
                '- / : ; ( ) & @ " *',
                '{abc} . , ? ! \' {backspace}',
                '{abc} {space} . {done}'
            ],
            'special': [
                '\u00e4 \u00f6 \u00fc \u00df \u00e0 \u00e1 \u00e2 \u00e8 \u00e9 \u00ea',
                '\u00f1 \u00f2 \u00f3 \u00f4 \u00f9 \u00fa \u00fb \u00fd \u00e7 \u00f0',
                '{abc} {space} {backspace}',
                '{abc} {space} . {done}'
            ]
        },
        display: {
            '{backspace}': '\u232b',
            '{shift}': '\u21e7',
            '{lock}': '\u21e7',
            '{space}': ' ',
            '{done}': 'Done',
            '{numbers}': '123',
            '{abc}': 'ABC',
            '{special}': '\u00e0\u00fc'
        },
        theme: 'hg-theme-default hg-layout-default quiz-kbd',
        mergeDisplay: true
    });

    function switchLayout(name) {
        layoutChanging = true;
        kbd.setOptions({ layoutName: name });
        setTimeout(() => { layoutChanging = false; }, 100);
    }

    function showKeyboard(input) {
        activeInput = input;
        kbd.setInput(input.value);
        kbd.setOptions({ layoutName: 'default' });
        kbdWrap.classList.remove('hidden');
        document.body.classList.add('kbd-open');
        setTimeout(() => input.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
    }

    function hideKeyboard() {
        kbdWrap.classList.add('hidden');
        document.body.classList.remove('kbd-open');
        if (activeInput) activeInput.blur();
        activeInput = null;
    }

    document.querySelectorAll('input[type="text"]').forEach(input => {
        input.addEventListener('focus', () => showKeyboard(input));
        input.setAttribute('inputmode', 'none');
    });

    document.addEventListener('pointerdown', e => {
        if (layoutChanging || ignoreNextDismiss) return;
        if (!kbdWrap.contains(e.target) && !e.target.matches('input')) {
            hideKeyboard();
        }
    });

    window.quizKbd = {
        setInput: val => kbd.setInput(val),
        suppressDismiss: () => { ignoreNextDismiss = true; setTimeout(() => { ignoreNextDismiss = false; }, 200); },
        getActiveInput: () => activeInput
    };
})();
