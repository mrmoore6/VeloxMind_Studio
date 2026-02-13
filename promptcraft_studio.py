#!/usr/bin/env python3
"""
VeloxMind Studio
A streamlined GUI application for generating ML-optimized prompts for AI agents
using Perplexity AI to intelligently craft task-specific prompts with history and export features
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import os
import json
from datetime import datetime
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from spellchecker import SpellChecker
except ImportError:
    SpellChecker = None

from history_manager import HistoryManager


# ===== BLACK & GOLD COLOR PALETTE =====
# Primary colors
COLOR_BLACK = '#000000'
COLOR_DARK_BG = '#1a1a1a'
COLOR_DARKER_BG = '#0d0d0d'

# Gold accent colors
COLOR_GOLD = '#FFD700'
COLOR_GOLD_HOVER = '#FFA500'
COLOR_GOLD_PRESSED = '#D4AF37'
COLOR_GOLD_DISABLED = '#8B7355'

# Text colors
COLOR_TEXT_LIGHT = '#FFFFFF'
COLOR_TEXT_GOLD = '#FFD700'
COLOR_TEXT_DIM = '#999999'

# UI element colors
COLOR_INPUT_BG = '#2a2a2a'
COLOR_BORDER = '#333333'
COLOR_SELECTION = '#FFD700'

# ===== GOTHIC FONT CONFIGURATION =====
GOTHIC_FONT = 'Futura'  # Primary font for most text
GOTHIC_FONT_FALLBACK = 'Century Gothic'  # Fallback if primary not available
TITLE_FONT = 'Monster of South St'  # Special font for title only


class GoldButton(tk.Canvas):
    """Custom gold button widget with smooth animations for macOS"""
    def __init__(self, parent, text, command, width=200, height=40, font_size=12):
        super().__init__(parent, width=width, height=height, 
                        bg=COLOR_DARK_BG, highlightthickness=0, cursor="hand2")
        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.font_size = font_size
        self.is_hovered = False
        self.is_pressed = False
        self.is_disabled = False
        self.animation_id = None
        self.current_scale = 1.0
        self.target_scale = 1.0
        
        # Draw button
        self.draw_button()
        
        # Bind events
        self.bind('<Button-1>', self.on_press)
        self.bind('<ButtonRelease-1>', self.on_release)
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
    
    def draw_button(self):
        self.delete('all')
        
        # Smooth scale interpolation
        if abs(self.current_scale - self.target_scale) > 0.01:
            self.current_scale += (self.target_scale - self.current_scale) * 0.3
        else:
            self.current_scale = self.target_scale
        
        # Determine color based on state with smooth transitions
        if self.is_disabled:
            bg_color = COLOR_GOLD_DISABLED
            text_color = COLOR_TEXT_DIM
        elif self.is_pressed:
            bg_color = COLOR_GOLD_PRESSED  # Darker gold when pressed
            text_color = COLOR_BLACK
        elif self.is_hovered:
            bg_color = COLOR_GOLD_HOVER  # Orange-gold when hovered
            text_color = COLOR_BLACK
        else:
            bg_color = COLOR_GOLD  # Bright gold normal state
            text_color = COLOR_BLACK
        
        # Calculate scaled dimensions for subtle animation
        scale = self.current_scale
        scaled_width = self.width * scale
        scaled_height = self.height * scale
        offset_x = (self.width - scaled_width) / 2
        offset_y = (self.height - scaled_height) / 2
        
        # Draw rectangle with animation
        self.create_rectangle(
            2 + offset_x, 2 + offset_y, 
            self.width - 2 - offset_x, self.height - 2 - offset_y,
            fill=bg_color, outline='', tags='button'
        )
        
        # Draw text
        self.create_text(self.width//2, self.height//2, 
                        text=self.text, fill=text_color, 
                        font=(GOTHIC_FONT, self.font_size, 'bold'), tags='text')
    
    def animate_transition(self, duration_ms=300):
        """Smooth transition animation with 300ms duration"""
        if self.animation_id:
            self.after_cancel(self.animation_id)
        
        steps = 10
        step_duration = duration_ms // steps
        
        def step(current_step):
            if current_step < steps:
                self.draw_button()
                self.animation_id = self.after(step_duration, lambda: step(current_step + 1))
            else:
                self.draw_button()
                self.animation_id = None
        
        step(0)
    
    def on_press(self, event):
        if not self.is_disabled:
            self.is_pressed = True
            self.target_scale = 0.95
            self.animate_transition(200)  # Quick press animation
    
    def on_release(self, event):
        if not self.is_disabled:
            self.is_pressed = False
            self.target_scale = 1.0 if self.is_hovered else 1.0
            self.animate_transition(300)
            if self.is_hovered and self.command:
                # Delay command execution slightly for visual feedback
                self.after(50, self.command)
    
    def on_enter(self, event):
        if not self.is_disabled:
            self.is_hovered = True
            self.target_scale = 1.02
            self.animate_transition(300)  # Smooth hover transition
    
    def on_leave(self, event):
        self.is_hovered = False
        self.is_pressed = False
        self.target_scale = 1.0
        self.animate_transition(300)  # Smooth return to normal
    
    def config(self, **kwargs):
        if 'state' in kwargs:
            if kwargs['state'] == 'disabled' or kwargs['state'] == tk.DISABLED:
                self.is_disabled = True
            else:
                self.is_disabled = False
            self.draw_button()
        if 'text' in kwargs:
            self.text = kwargs['text']
            self.draw_button()


class SpellCheckDialog(tk.Toplevel):
    """Dialog for displaying and managing spelling corrections"""
    def __init__(self, parent, errors, original_text, apply_callback):
        super().__init__(parent)
        self.title("Spell Check")
        self.geometry("700x500")
        self.configure(bg=COLOR_DARK_BG)
        
        self.errors = errors
        self.original_text = original_text
        self.apply_callback = apply_callback
        self.corrections = []
        self.ignored_indices = set()
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Title
        title_label = tk.Label(
            self,
            text=f"Found {len(self.errors)} spelling error(s)",
            font=(GOTHIC_FONT, 14, "bold"),
            bg=COLOR_DARK_BG,
            fg=COLOR_TEXT_GOLD
        )
        title_label.pack(pady=10)
        
        # Scrollable frame for errors
        canvas_frame = tk.Frame(self, bg=COLOR_DARK_BG)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame, bg=COLOR_DARK_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_DARK_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create error entries
        for idx, error in enumerate(self.errors):
            self.create_error_entry(scrollable_frame, idx, error)
        
        # Bottom button frame
        button_frame = tk.Frame(self, bg=COLOR_DARK_BG)
        button_frame.pack(pady=10)
        
        # Apply All button
        apply_all_btn = GoldButton(
            button_frame,
            text="Apply All",
            command=self.apply_all,
            width=120,
            height=40,
            font_size=11
        )
        apply_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_btn = GoldButton(
            button_frame,
            text="Close",
            command=self.destroy,
            width=100,
            height=40,
            font_size=11
        )
        close_btn.pack(side=tk.LEFT, padx=5)
    
    def create_error_entry(self, parent, idx, error):
        """Create a single error entry with suggestions"""
        entry_frame = tk.Frame(parent, bg=COLOR_INPUT_BG, relief=tk.RAISED, borderwidth=1)
        entry_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Error info
        info_frame = tk.Frame(entry_frame, bg=COLOR_INPUT_BG)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Misspelled word
        word_label = tk.Label(
            info_frame,
            text=f"Misspelled: ",
            font=(GOTHIC_FONT, 10),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT_DIM
        )
        word_label.pack(side=tk.LEFT)
        
        word_value = tk.Label(
            info_frame,
            text=error['word'],
            font=(GOTHIC_FONT, 10, "bold"),
            bg=COLOR_INPUT_BG,
            fg=COLOR_GOLD
        )
        word_value.pack(side=tk.LEFT)
        
        # Context
        context_label = tk.Label(
            entry_frame,
            text=f"Context: {error['context']}",
            font=(GOTHIC_FONT, 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT_DIM,
            wraplength=600,
            justify=tk.LEFT
        )
        context_label.pack(fill=tk.X, padx=10, pady=2)
        
        # Suggestions frame
        suggestions_frame = tk.Frame(entry_frame, bg=COLOR_INPUT_BG)
        suggestions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Suggestion dropdown
        suggestion_var = tk.StringVar()
        if error['suggestions']:
            suggestion_var.set(error['suggestions'][0])
        
        suggestion_label = tk.Label(
            suggestions_frame,
            text="Suggestion:",
            font=(GOTHIC_FONT, 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT_LIGHT
        )
        suggestion_label.pack(side=tk.LEFT, padx=(0, 5))
        
        suggestion_menu = tk.OptionMenu(
            suggestions_frame,
            suggestion_var,
            *error['suggestions']
        )
        suggestion_menu.config(
            bg=COLOR_DARKER_BG,
            fg=COLOR_TEXT_LIGHT,
            activebackground=COLOR_GOLD,
            activeforeground=COLOR_BLACK,
            highlightthickness=0
        )
        suggestion_menu.pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = tk.Frame(suggestions_frame, bg=COLOR_INPUT_BG)
        btn_frame.pack(side=tk.RIGHT)
        
        # Apply button
        apply_btn = GoldButton(
            btn_frame,
            text="Apply",
            command=lambda: self.apply_single(idx, error, suggestion_var.get()),
            width=80,
            height=30,
            font_size=9
        )
        apply_btn.pack(side=tk.LEFT, padx=2)
        
        # Ignore button
        ignore_btn = GoldButton(
            btn_frame,
            text="Ignore",
            command=lambda: self.ignore_single(idx, entry_frame),
            width=80,
            height=30,
            font_size=9
        )
        ignore_btn.pack(side=tk.LEFT, padx=2)
    
    def apply_single(self, idx, error, replacement):
        """Apply a single correction"""
        if idx not in self.ignored_indices:
            self.corrections.append({
                'start': error['start'],
                'end': error['end'],
                'replacement': replacement
            })
            self.ignored_indices.add(idx)
            
            # Apply immediately
            self.apply_callback([self.corrections[-1]])
            
            # Update display
            messagebox.showinfo("Applied", f"Replaced '{error['word']}' with '{replacement}'")
    
    def ignore_single(self, idx, frame):
        """Ignore a single error"""
        self.ignored_indices.add(idx)
        frame.configure(bg=COLOR_DARKER_BG)
        
        # Disable all widgets in frame
        for widget in frame.winfo_children():
            if hasattr(widget, 'config'):
                try:
                    widget.config(state=tk.DISABLED)
                except:
                    pass
    
    def apply_all(self):
        """Apply all corrections at once"""
        corrections_to_apply = []
        
        for idx, error in enumerate(self.errors):
            if idx not in self.ignored_indices and error['suggestions']:
                corrections_to_apply.append({
                    'start': error['start'],
                    'end': error['end'],
                    'replacement': error['suggestions'][0]  # Use first suggestion
                })
        
        if corrections_to_apply:
            self.apply_callback(corrections_to_apply)
            self.destroy()
        else:
            messagebox.showinfo("No Corrections", "No corrections to apply.")


class AIPromptGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("VeloxMind Studio")
        self.root.geometry("1200x850")
        
        # Set dark background color
        self.bg_color = "#1a1a1a"
        self.text_color = "#ffffff"
        
        self.root.configure(bg=self.bg_color)
        
        # Initialize managers
        self.history_manager = HistoryManager()
        
        # Current state
        self.last_generated_prompt = ""
        
        # Prompt cache for consistency
        self.prompt_cache = {}  # Maps input text -> generated prompt
        self.last_input_text = ""  # Track last input
        
        # Conversation memory for context persistence
        self.conversation_history = []  # List of {role: str, content: str} messages
        self.conversation_file = None  # Will be set after init
        self.max_conversation_turns = 50  # Keep last 50 turns
        
        # Initialize Perplexity client
        self.init_perplexity_client()
        
        # Initialize spell checker
        self.init_spell_checker()
        
        # Initialize conversation memory
        self.init_conversation_memory()
        
        # Create GUI elements
        self.create_widgets()
    
    def init_perplexity_client(self):
        """Initialize the AI API client (OpenAI or Anthropic)"""
        try:
            # Try OpenAI first (primary)
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key and OpenAI is not None:
                self.client = OpenAI(api_key=openai_key)
                self.client_type = 'openai'
                self.model = 'gpt-4o-mini'  # Fast and cost-effective
                return
            
            # Try Anthropic as fallback
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_key and Anthropic is not None:
                self.client = Anthropic(api_key=anthropic_key)
                self.client_type = 'anthropic'
                self.model = 'claude-3-5-sonnet-20241022'
                return
            
            # No API keys found
            if not openai_key and not anthropic_key:
                messagebox.showwarning(
                    "API Key Missing",
                    "No API keys found.\n\n"
                    "Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your environment.\n\n"
                    "You can still use the app, but generation will use simple fallback."
                )
            elif OpenAI is None and Anthropic is None:
                messagebox.showerror(
                    "Package Missing",
                    "Neither 'openai' nor 'anthropic' package is installed.\n\n"
                    "Please install one using:\n"
                    "pip3 install openai\n"
                    "or\n"
                    "pip3 install anthropic"
                )
            
            self.client = None
            self.client_type = None
            self.model = None
            
        except Exception as e:
            messagebox.showerror("Initialization Error", 
                               f"Failed to initialize AI client: {str(e)}")
            self.client = None
            self.client_type = None
            self.model = None
    
    def init_spell_checker(self):
        """Initialize the spell checker"""
        if SpellChecker is None:
            self.spell_checker = None
        else:
            try:
                self.spell_checker = SpellChecker()
            except Exception as e:
                self.spell_checker = None
    
    def init_conversation_memory(self):
        """Initialize conversation memory system"""
        # Set up conversation file path
        home = os.path.expanduser('~')
        conversation_dir = os.path.join(home, '.veloxmind_studio')
        os.makedirs(conversation_dir, exist_ok=True)
        self.conversation_file = os.path.join(conversation_dir, 'conversation.json')
        
        # Load existing conversation if available
        self.load_conversation()
    
    def load_conversation(self):
        """Load conversation history from file"""
        if not os.path.exists(self.conversation_file):
            self.conversation_history = []
            return
        
        try:
            with open(self.conversation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.conversation_history = data.get('messages', [])
        except Exception as e:
            print(f"Error loading conversation: {e}")
            self.conversation_history = []
    
    def save_conversation(self):
        """Save conversation history to file"""
        try:
            # Trim conversation if too long
            if len(self.conversation_history) > self.max_conversation_turns * 2:
                # Keep last N turns (each turn = user + assistant message)
                self.conversation_history = self.conversation_history[-(self.max_conversation_turns * 2):]
            
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'messages': self.conversation_history
            }
            with open(self.conversation_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving conversation: {e}")
    
    def add_to_conversation(self, role: str, content: str):
        """Add a message to conversation history"""
        self.conversation_history.append({
            'role': role,
            'content': content
        })
        self.save_conversation()
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.save_conversation()
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation for display"""
        if not self.conversation_history:
            return "No conversation context"
        
        turn_count = len([m for m in self.conversation_history if m['role'] == 'user'])
        return f"{turn_count} turn(s) in context"
    
    def clear_conversation_ui(self):
        """Clear conversation context and update UI"""
        if self.conversation_history:
            if messagebox.askyesno("Clear Context", 
                                  "Clear conversation context? The AI will forget previous details."):
                self.clear_conversation()
                self.update_context_status()
                messagebox.showinfo("Context Cleared", "Conversation context has been cleared.")
        else:
            messagebox.showinfo("No Context", "No conversation context to clear.")
    
    def update_context_status(self):
        """Update the context status label"""
        if hasattr(self, 'context_status_label'):
            self.context_status_label.config(text=self.get_conversation_summary())
    
    def create_widgets(self):
        """Create and layout all GUI widgets"""
        
        # Main container with two columns
        main_container = tk.Frame(self.root, bg=self.bg_color)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel (main content)
        left_panel = tk.Frame(main_container, bg=self.bg_color)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Right panel (history)
        right_panel = tk.Frame(main_container, bg=self.bg_color, width=250)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # === LEFT PANEL ===
        
        # Title Label
        title_label = tk.Label(
            left_panel,
            text="VeloxMind Studio",
            font=(TITLE_FONT, 18, "bold"),
            bg=self.bg_color,
            fg=self.text_color
        )
        title_label.pack(pady=(0, 10))
        
        # Subtitle
        subtitle_label = tk.Label(
            left_panel,
            text="AI Assistant with Conversation Memory - remembers context across prompts",
            font=(GOTHIC_FONT, 10),
            bg=self.bg_color,
            fg=COLOR_TEXT_GOLD
        )
        subtitle_label.pack(pady=(0, 15))
        
        # Input Frame
        input_frame = tk.Frame(left_panel, bg=self.bg_color)
        input_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        input_label = tk.Label(
            input_frame,
            text="Your Task/Idea:",
            font=(GOTHIC_FONT, 11, "bold"),
            bg=self.bg_color,
            fg=self.text_color
        )
        input_label.pack(anchor=tk.W)
        
        # Input Text Area
        self.input_text = scrolledtext.ScrolledText(
            input_frame,
            height=6,
            font=(GOTHIC_FONT, 11),
            bg=COLOR_INPUT_BG,
            fg=self.text_color,
            insertbackground=COLOR_GOLD,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            wrap=tk.WORD
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Control buttons
        control_frame = tk.Frame(left_panel, bg=self.bg_color)
        control_frame.pack(pady=10)
        
        # Generate Button
        self.generate_button = GoldButton(
            control_frame,
            text="Generate Prompt",
            command=self.generate_prompt,
            width=200,
            height=45,
            font_size=13
        )
        self.generate_button.pack(side=tk.LEFT, padx=5)
        
        # Save Prompt Button
        self.save_prompt_button = GoldButton(
            control_frame,
            text="Save Prompt",
            command=self.save_current_prompt,
            width=150,
            height=45,
            font_size=11
        )
        self.save_prompt_button.pack(side=tk.LEFT, padx=5)
        
        # Spell Check Button (Auto-correct)
        self.spell_check_button_top = GoldButton(
            control_frame,
            text="Spell Check",
            command=self.auto_spell_check,
            width=150,
            height=45,
            font_size=11
        )
        self.spell_check_button_top.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        self.clear_button = GoldButton(
            control_frame,
            text="Clear",
            command=self.clear_input,
            width=120,
            height=45,
            font_size=11
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Output Frame
        output_frame = tk.Frame(left_panel, bg=self.bg_color)
        output_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        output_label = tk.Label(
            output_frame,
            text="Generated Prompt:",
            font=(GOTHIC_FONT, 11, "bold"),
            bg=self.bg_color,
            fg=self.text_color
        )
        output_label.pack(anchor=tk.W)
        
        # Output Text Area
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            height=12,
            font=(GOTHIC_FONT, 10),
            bg=COLOR_INPUT_BG,
            fg=self.text_color,
            insertbackground=COLOR_GOLD,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Button Frame for additional actions
        button_frame = tk.Frame(left_panel, bg=self.bg_color)
        button_frame.pack(pady=10)
        
        # Copy Button
        self.copy_button = GoldButton(
            button_frame,
            text="Copy to Clipboard",
            command=self.copy_to_clipboard,
            width=180,
            height=40,
            font_size=11
        )
        self.copy_button.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        self.clear_button = GoldButton(
            button_frame,
            text="Clear All",
            command=self.clear_all,
            width=120,
            height=40,
            font_size=11
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Export Button
        self.export_button = GoldButton(
            button_frame,
            text="Export",
            command=self.export_prompt,
            width=100,
            height=40,
            font_size=11
        )
        self.export_button.pack(side=tk.LEFT, padx=5)
        
        # === RIGHT PANEL (Conversation Context & History) ===
        
        # Conversation Context Section
        context_section = tk.Frame(right_panel, bg=self.bg_color)
        context_section.pack(pady=(0, 10), fill=tk.X)
        
        context_title = tk.Label(
            context_section,
            text="Conversation Context",
            font=(GOTHIC_FONT, 12, "bold"),
            bg=self.bg_color,
            fg=COLOR_TEXT_GOLD
        )
        context_title.pack(pady=(0, 5))
        
        # Context status label
        self.context_status_label = tk.Label(
            context_section,
            text=self.get_conversation_summary(),
            font=(GOTHIC_FONT, 9),
            bg=self.bg_color,
            fg=COLOR_TEXT_DIM
        )
        self.context_status_label.pack(pady=(0, 5))
        
        # Clear context button
        clear_context_btn = GoldButton(
            context_section,
            text="Clear Context",
            command=self.clear_conversation_ui,
            width=150,
            height=30,
            font_size=9
        )
        clear_context_btn.pack(pady=5)
        
        # Separator
        separator = tk.Frame(right_panel, bg=COLOR_BORDER, height=2)
        separator.pack(fill=tk.X, pady=10)
        
        history_title = tk.Label(
            right_panel,
            text="History",
            font=(GOTHIC_FONT, 14, "bold"),
            bg=self.bg_color,
            fg=self.text_color
        )
        history_title.pack(pady=(0, 10))
        
        # History listbox with scrollbar
        history_list_frame = tk.Frame(right_panel, bg=self.bg_color)
        history_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        history_scrollbar = tk.Scrollbar(history_list_frame)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.history_listbox = tk.Listbox(
            history_list_frame,
            bg=COLOR_INPUT_BG,
            fg=self.text_color,
            selectbackground=COLOR_GOLD,
            selectforeground=COLOR_BLACK,
            font=(GOTHIC_FONT, 9),
            yscrollcommand=history_scrollbar.set,
            activestyle='none'
        )
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.config(command=self.history_listbox.yview)
        
        self.history_listbox.bind('<<ListboxSelect>>', self.on_history_select)
        
        # History buttons
        history_btn_frame = tk.Frame(right_panel, bg=self.bg_color)
        history_btn_frame.pack(pady=10)
        
        load_btn = GoldButton(
            history_btn_frame,
            text="Load",
            command=self.load_from_history,
            width=70,
            height=30,
            font_size=9
        )
        load_btn.pack(side=tk.LEFT, padx=2)
        
        delete_btn = GoldButton(
            history_btn_frame,
            text="Delete",
            command=self.delete_from_history,
            width=70,
            height=30,
            font_size=9
        )
        delete_btn.pack(side=tk.LEFT, padx=2)
        
        clear_hist_btn = GoldButton(
            history_btn_frame,
            text="Clear",
            command=self.clear_history,
            width=70,
            height=30,
            font_size=9
        )
        clear_hist_btn.pack(side=tk.LEFT, padx=2)
        
        # Load history into listbox
        self.refresh_history_list()
    
    def validate_and_sanitize_input(self, text: str) -> str:
        """Validate and sanitize user input"""
        # Strip whitespace
        text = text.strip()
        
        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive whitespace
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Remove multiple consecutive blank lines
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
        
        return text
    
    def build_universal_prompt(self, user_input: str) -> str:
        """
        Simplified fallback prompt builder - concise and AI-optimized.
        Used when ML generation is unavailable.
        """
        # Return user input as-is, keeping it simple
        return user_input
    
    def generate_prompt(self):
        """Generate an optimized prompt using ML"""
        # Get and validate input text
        user_input = self.input_text.get("1.0", tk.END)
        user_input = self.validate_and_sanitize_input(user_input)
        
        if not user_input:
            messagebox.showwarning("Input Required", 
                                 "Please enter a topic or idea first.")
            return
        
        # Check if API client is available
        if not self.client:
            messagebox.showwarning(
                "API Not Available",
                "Perplexity API is not configured. Using rule-based generation instead."
            )
            # Fallback to rule-based generation
            final_prompt = self.build_universal_prompt(user_input)
            self.display_prompt(final_prompt, user_input)
            return
        
        # Use ML to generate the prompt
        self.generate_button.config(state=tk.DISABLED, text="Generating...")
        self.root.update()
        
        try:
            # Use Perplexity to intelligently analyze and generate prompt
            ml_prompt = self.generate_ml_prompt(user_input)
            self.display_prompt(ml_prompt, user_input)
        except Exception as e:
            messagebox.showerror("Generation Error", 
                               f"ML generation failed: {str(e)}\n\nUsing rule-based fallback.")
            # Fallback to rule-based
            final_prompt = self.build_universal_prompt(user_input)
            self.display_prompt(final_prompt, user_input)
        finally:
            self.generate_button.config(state=tk.NORMAL, text="Generate Prompt")
    
    def display_prompt(self, prompt: str, user_input: str):
        """Display the generated prompt and save to history"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", prompt)
        self.output_text.config(state=tk.DISABLED)
        
        self.last_generated_prompt = prompt
        
        # Add to history
        self.history_manager.add_entry(
            user_input, 
            prompt, 
            'ml_generated'
        )
        self.refresh_history_list()
        
        # Update context status
        self.update_context_status()
    
    def analyze_input_with_ml(self, user_input: str) -> dict:
        """Simplified analysis - no longer needed with new approach"""
        # Return basic analysis without API call
        return {
            "task_type": "general",
            "requirements": []
        }
    
    def generate_ml_prompt(self, user_input: str) -> str:
        """Use ML (OpenAI or Anthropic) to execute the user's request with conversation context"""
        
        # System prompt for AI assistant behavior
        system_prompt = """Transform the user's input into a clear, AI-ready prompt. Follow their input as closely as possible - preserve their exact intent, wording, and all specific details. Make it detailed enough to be actionable but concise. Use context from previous messages. Don't add extra information not requested by the user."""
        
        try:
            # Build messages list with conversation history
            messages = []
            
            # Add conversation history for context
            for msg in self.conversation_history:
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
            
            # Add current user input
            messages.append({
                'role': 'user',
                'content': user_input
            })
            
            if self.client_type == 'openai':
                # OpenAI API call with conversation context
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt}
                    ] + messages,
                    max_completion_tokens=2000
                )
                ai_response = response.choices[0].message.content
                
            elif self.client_type == 'anthropic':
                # Anthropic API call with conversation context
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=messages
                )
                ai_response = response.content[0].text
            
            else:
                # No API available, use fallback
                return self.build_universal_prompt(user_input)
            
            # Add to conversation history
            self.add_to_conversation('user', user_input)
            self.add_to_conversation('assistant', ai_response)
            
            return ai_response

        except Exception as e:
            # On error, use fallback
            print(f"API Error: {e}")
            return self.build_universal_prompt(user_input)

    
    def show_preview(self, final_prompt: str):
        """Show preview of the prompt that would be sent"""
        preview_text = f"""=== PROMPT THAT WILL BE SENT ===

{final_prompt}

=== NOTE ===
This is a preview. Uncheck 'Preview before sending' to actually generate."""
        
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", preview_text)
        self.output_text.config(state=tk.DISABLED)
        
        self.last_generated_prompt = preview_text
    
    def send_to_api(self, final_prompt: str, user_input: str):
        """Send prompt to Perplexity API"""
        if not self.client:
            messagebox.showerror("API Error", 
                               "Perplexity client not initialized. "
                               "Please check your API key.")
            return
        
        # Disable button during generation
        self.generate_button.config(state=tk.DISABLED, text="Generating...")
        self.root.update()
        
        try:
            # Call Perplexity API with a simple, direct system prompt
            response = self.client.chat.completions.create(
                model="sonar",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful AI assistant that provides clear, accurate, and well-structured responses."
                    },
                    {
                        "role": "user", 
                        "content": final_prompt
                    }
                ]
            )
            
            # Extract the generated response
            generated_response = response.choices[0].message.content
            
            # Display the result
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", generated_response)
            self.output_text.config(state=tk.DISABLED)
            
            self.last_generated_prompt = generated_response
            
            # Add to history
            self.history_manager.add_entry(
                user_input, 
                generated_response, 
                'universal'
            )
            self.refresh_history_list()
            
        except Exception as e:
            messagebox.showerror("Generation Error", 
                               f"Failed to generate response: {str(e)}")
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", f"Error: {str(e)}")
            self.output_text.config(state=tk.DISABLED)
        
        finally:
            # Re-enable button
            self.generate_button.config(state=tk.NORMAL, text="Generate Prompt")
    
    def copy_to_clipboard(self):
        """Copy the generated prompt to clipboard"""
        output_content = self.output_text.get("1.0", tk.END).strip()
        
        if not output_content or output_content.startswith("Error:"):
            messagebox.showwarning("Nothing to Copy", "No valid content to copy.")
            return
        
        self.root.clipboard_clear()
        self.root.clipboard_append(output_content)
        messagebox.showinfo("Copied", "Content copied to clipboard!")
    
    def clear_all(self):
        """Clear all text fields"""
        self.input_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.last_generated_prompt = ""
    
    def clear_input(self):
        """Clear only the input text field"""
        self.input_text.delete("1.0", tk.END)
        self.input_text.focus_set()
    
    def save_current_prompt(self):
        """Save current prompt to a file"""
        output_content = self.output_text.get("1.0", tk.END).strip()
        
        if not output_content:
            messagebox.showwarning("Nothing to Save", "No content to save.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All files", "*.*")
            ],
            title="Save Prompt"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(output_content)
                messagebox.showinfo("Saved", f"Content saved to {filename}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save: {str(e)}")
    
    def export_prompt(self):
        """Export prompt with metadata to JSON"""
        output_content = self.output_text.get("1.0", tk.END).strip()
        input_content = self.input_text.get("1.0", tk.END).strip()
        
        if not output_content:
            messagebox.showwarning("Nothing to Export", "No content to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ],
            title="Export Prompt"
        )
        
        if filename:
            try:
                data = {
                    'user_input': input_content,
                    'generated_response': output_content,
                    'timestamp': datetime.now().isoformat(),
                    'version': '2.0'
                }
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Exported", f"Content exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def refresh_history_list(self):
        """Refresh the history listbox"""
        self.history_listbox.delete(0, tk.END)
        
        history = self.history_manager.get_history(limit=50)
        for entry in history:
            self.history_listbox.insert(tk.END, entry.get_display_text())
    
    def on_history_select(self, event):
        """Handle history item selection"""
        # Just highlight, don't load automatically
        pass
    
    def load_from_history(self):
        """Load selected history entry"""
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a history item first.")
            return
        
        index = selection[0]
        entry = self.history_manager.get_entry(index)
        
        if entry:
            # Load input
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", entry.user_input)
            
            # Load output
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", entry.generated_prompt)
            self.output_text.config(state=tk.DISABLED)
    
    def delete_from_history(self):
        """Delete selected history entry"""
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a history item first.")
            return
        
        index = selection[0]
        if messagebox.askyesno("Confirm Delete", "Delete this history entry?"):
            self.history_manager.delete_entry(index)
            self.refresh_history_list()
    
    def clear_history(self):
        """Clear all history"""
        if messagebox.askyesno("Confirm Clear", 
                              "Clear all history? This cannot be undone."):
            self.history_manager.clear_history()
            self.refresh_history_list()
    
    def spell_check_prompt(self):
        """Check spelling in the input task/idea text"""
        # Get text from input area
        input_content = self.input_text.get("1.0", tk.END).strip()
        
        if not input_content:
            messagebox.showwarning("Nothing to Check", "No text to spell check.")
            return
        
        # Check if spell checker is available
        if self.spell_checker is None:
            messagebox.showerror(
                "Spell Checker Not Available",
                "The 'pyspellchecker' package is not installed.\n\n"
                "Please install it using:\n"
                "pip3 install pyspellchecker"
            )
            return
        
        # Extract words and check spelling
        errors = self.find_spelling_errors(input_content)
        
        if not errors:
            messagebox.showinfo("Spell Check", "No spelling errors found!")
            return
        
        # Show spell check dialog
        SpellCheckDialog(self.root, errors, input_content, self.apply_corrections)
    
    def auto_spell_check(self):
        """Automatically check and correct all spelling errors without showing dialog"""
        # Get text from INPUT area
        input_content = self.input_text.get("1.0", tk.END).strip()
        
        if not input_content:
            messagebox.showwarning("Nothing to Check", "No text to spell check.")
            return
        
        # Check if spell checker is available
        if self.spell_checker is None:
            messagebox.showerror(
                "Spell Checker Not Available",
                "The 'pyspellchecker' package is not installed.\n\n"
                "Please install it using:\n"
                "pip3 install pyspellchecker"
            )
            return
        
        # Find spelling errors
        errors = self.find_spelling_errors(input_content)
        
        if not errors:
            messagebox.showinfo("Spell Check", "No spelling errors found!")
            return
        
        # Automatically apply all corrections
        corrections = []
        for error in errors:
            suggestions = error['suggestions']
            suggestion = suggestions[0] if suggestions else error['word']  # Use first suggestion
            corrections.append({
                'start': error['start'],
                'end': error['end'],
                'replacement': suggestion
            })
        
        # Apply all corrections (apply_corrections will show success message)
        self.apply_corrections(corrections)
    
    def find_spelling_errors(self, text):
        """Find spelling errors in text and return list of errors with suggestions"""
        errors = []
        
        # Split text into words while preserving positions
        word_pattern = re.compile(r'\b[a-zA-Z]+\b')
        
        for match in word_pattern.finditer(text):
            word = match.group()
            start_pos = match.start()
            end_pos = match.end()
            
            # Skip very short words and common abbreviations
            if len(word) <= 2:
                continue
            
            # Check if word is misspelled
            if word.lower() not in self.spell_checker:
                # Get suggestions
                candidates = self.spell_checker.candidates(word)
                if candidates:  # Check if candidates is not None
                    suggestions = list(candidates)
                    if suggestions:
                        errors.append({
                            'word': word,
                            'start': start_pos,
                            'end': end_pos,
                            'suggestions': suggestions[:5],  # Limit to top 5 suggestions
                            'context': self.get_word_context(text, start_pos, end_pos)
                        })
        
        return errors
    
    def get_word_context(self, text, start, end):
        """Get context around a word for display"""
        context_start = max(0, start - 20)
        context_end = min(len(text), end + 20)
        context = text[context_start:context_end]
        
        # Add ellipsis if truncated
        if context_start > 0:
            context = '...' + context
        if context_end < len(text):
            context = context + '...'
        
        return context
    
    def apply_corrections(self, corrections):
        """Apply spelling corrections to the input text"""
        input_content = self.input_text.get("1.0", tk.END).strip()
        
        # Sort corrections by position (reverse order to maintain positions)
        sorted_corrections = sorted(corrections, key=lambda x: x['start'], reverse=True)
        
        # Apply each correction
        for correction in sorted_corrections:
            input_content = (
                input_content[:correction['start']] + 
                correction['replacement'] + 
                input_content[correction['end']:]
            )
        
        # Update input text
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", input_content)
        
        messagebox.showinfo("Corrections Applied", 
                          f"{len(corrections)} correction(s) applied successfully!")


def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = AIPromptGenerator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
