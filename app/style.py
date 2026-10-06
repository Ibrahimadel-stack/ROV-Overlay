"""Dark theme stylesheet for the control window."""

DARK_QSS = """
* { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }

QWidget {
    background-color: #1a1a2e;
    color: #e6e6ef;
}

QMainWindow, QDialog { background-color: #1a1a2e; }

QTabWidget::pane {
    border: 1px solid #0f3460;
    background: #16213e;
    border-radius: 6px;
}
QTabBar::tab {
    background: #16213e;
    color: #9aa4c0;
    padding: 9px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #0f3460;
    color: #ffffff;
    border-bottom: 2px solid #e94560;
}
QTabBar::tab:hover { background: #1d2b50; }

QGroupBox {
    border: 1px solid #0f3460;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: 600;
    color: #c7d0ec;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #e94560;
}

QPushButton {
    background-color: #0f3460;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover { background-color: #16498a; }
QPushButton:pressed { background-color: #0c2847; }
QPushButton:disabled { background-color: #2a2a3e; color: #666; }

QPushButton#accent {
    background-color: #e94560;
}
QPushButton#accent:hover { background-color: #ff5c77; }

QPushButton#danger { background-color: #8c2a3a; }
QPushButton#danger:hover { background-color: #b23148; }

QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #0e1630;
    border: 1px solid #0f3460;
    border-radius: 5px;
    padding: 5px 8px;
    color: #e6e6ef;
    selection-background-color: #e94560;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #e94560;
}

QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #0e1630;
    border: 1px solid #0f3460;
    selection-background-color: #0f3460;
    color: #e6e6ef;
}

QListWidget, QTableWidget, QTreeWidget {
    background-color: #0e1630;
    border: 1px solid #0f3460;
    border-radius: 6px;
    alternate-background-color: #121c3a;
}
QListWidget::item { padding: 7px; border-radius: 4px; }
QListWidget::item:selected { background: #0f3460; color: #fff; }
QListWidget::item:hover { background: #1d2b50; }

QTableWidget { gridline-color: #233; }
QHeaderView::section {
    background-color: #0f3460;
    color: #cdd6f4;
    padding: 6px;
    border: none;
    font-weight: 600;
}
QTableWidget::item:selected { background: #0f3460; }

QScrollBar:vertical { background: #11182f; width: 12px; border-radius: 6px; }
QScrollBar::handle:vertical { background: #0f3460; border-radius: 6px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #16498a; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal { background: #11182f; height: 12px; border-radius: 6px; }
QScrollBar::handle:horizontal { background: #0f3460; border-radius: 6px; min-width: 24px; }

QLabel#status_connected { color: #38d66b; font-weight: 700; }
QLabel#status_disconnected { color: #e94560; font-weight: 700; }
QLabel#heading { font-size: 15px; font-weight: 700; color: #ffffff; }
QLabel#subtle { color: #8a93b2; }

QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #0f3460; background: #0e1630;
}
QCheckBox::indicator:checked { background: #e94560; border: 1px solid #e94560; }

QMenu { background: #16213e; border: 1px solid #0f3460; }
QMenu::item:selected { background: #0f3460; }

QToolTip { background: #0e1630; color: #e6e6ef; border: 1px solid #e94560; }
"""
