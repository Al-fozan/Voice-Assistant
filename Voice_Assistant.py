import tkinter as tk
from tkinter import ttk, scrolledtext
import cohere
import whisper
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import os
import io
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import threading
import queue
import platform
import subprocess
import time
import re

class VoiceAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Assistant")
        self.root.geometry("750x600")
        self.root.configure(bg='#F8F9FA')
        self.root.resizable(True, True)
        
        # Initialize AI components
        self.model = whisper.load_model("medium")
        self.co = cohere.Client("YOUR_COHERE_API_KEY")  # Replace with your key
        
        # Audio control
        self.audio_queue = queue.Queue()
        self.playback_active = False
        self.stop_playback_flag = False
        self.speaking_active = False
        self.recording_active = False
        self.recorded_audio = None
        self.sample_rate = 16000
        
        # Settings
        self.current_language = "ar"  # Default to Arabic for this focused solution
        self.current_model = "medium"  # whisper model
        self.available_models = ["tiny", "base", "small", "medium", "large"]
        
        # Create GUI
        self.create_widgets()
        
        # Start playback thread
        self.playback_thread = threading.Thread(target=self.playback_worker, daemon=True)
        self.playback_thread.start()

    def create_widgets(self):
        """Create all GUI components"""
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = ttk.Frame(self.root, padding=25)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title with improved styling
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 25))
        
        title_label = ttk.Label(title_frame, 
                                 text="🎙️ Voice Assistant", 
                                 font=('Segoe UI', 18, 'bold'),
                                 foreground='#2E3440')
        title_label.pack(side=tk.LEFT)
        
        # Settings button
        settings_btn = ttk.Button(title_frame,
                                  text="⚙️ Settings",
                                  command=self.open_settings)
        settings_btn.pack(side=tk.RIGHT)
        
        # Status bar with better styling
        self.status_var = tk.StringVar(value="Ready to record")
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        status_bar = ttk.Label(status_frame, 
                                 textvariable=self.status_var,
                                 relief=tk.SUNKEN,
                                 padding=8,
                                 font=('Segoe UI', 10))
        status_bar.pack(fill=tk.X)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=15)
        
        # Left side buttons
        left_btn_frame = ttk.Frame(btn_frame)
        left_btn_frame.pack(side=tk.LEFT)
        
        self.record_btn = ttk.Button(left_btn_frame, 
                                       text="🎤 Start Recording", 
                                       command=self.start_recording,
                                       style='Accent.TButton')
        self.record_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_record_btn = ttk.Button(left_btn_frame,
                                          text="⏹ Stop Recording",
                                          command=self.stop_recording,
                                          state=tk.DISABLED)
        self.stop_record_btn.pack(side=tk.LEFT, padx=5)
        
        # Stop speaking button
        self.stop_speaking_btn = ttk.Button(left_btn_frame,
                                            text="🔇 Stop Speaking",
                                            command=self.stop_speaking,
                                            state=tk.DISABLED)
        self.stop_speaking_btn.pack(side=tk.LEFT, padx=5)
        
        # Right side buttons
        right_btn_frame = ttk.Frame(btn_frame)
        right_btn_frame.pack(side=tk.RIGHT)
        
        self.clear_btn = ttk.Button(right_btn_frame,
                                     text="🗑️ Clear Chat",
                                     command=self.clear_chat)
        self.clear_btn.pack(side=tk.RIGHT, padx=5)
        
        # Text displays with improved styling
        self.input_frame = ttk.LabelFrame(main_frame, 
                                       text=f" 🗣️ Your Speech ({self.get_language_name()}) ", 
                                       padding=10)
        self.input_frame.pack(fill=tk.BOTH, pady=(0, 15), expand=True)
        
        self.input_text = scrolledtext.ScrolledText(self.input_frame,
                                                     height=6,
                                                     wrap=tk.WORD,
                                                     font=('Segoe UI', 10),
                                                     bg='#F5F5F5',
                                                     relief=tk.FLAT,
                                                     borderwidth=1)
        self.input_text.pack(fill=tk.BOTH, expand=True)
        
        self.output_frame = ttk.LabelFrame(main_frame, 
                                        text=f" 🤖 AI Response ({self.get_language_name()}) ", 
                                        padding=10)
        self.output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(self.output_frame,
                                                      height=6,
                                                      wrap=tk.WORD,
                                                      font=('Segoe UI', 10),
                                                      bg='#F0F8FF',
                                                      relief=tk.FLAT,
                                                      borderwidth=1)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar with improved styling
        self.progress = ttk.Progressbar(main_frame, 
                                         mode='indeterminate',
                                         style='TProgressbar')
        self.progress.pack(fill=tk.X, pady=(15, 0))
    
    def playback_worker(self):
        """Handle audio playback from queue"""
        while True:
            audio_bytes = self.audio_queue.get()
            if audio_bytes is None:
                break
                
            try:
                self.playback_active = True
                self.speaking_active = True
                self.stop_playback_flag = False
                
                # Update GUI in main thread
                self.root.after(0, self.enable_stop_buttons)
                
                # Create temporary file
                with open("temp_playback.mp3", "wb") as f:
                    f.write(audio_bytes.getvalue())
                
                # Play with system command for better control
                if platform.system() == "Windows":
                    self.playback_process = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "temp_playback.mp3"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    self.playback_process = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "temp_playback.mp3"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                
                # Wait for playback to complete or stop signal
                while self.playback_process.poll() is None:
                    if self.stop_playback_flag:
                        self.playback_process.terminate()
                        try:
                            self.playback_process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            self.playback_process.kill()
                        break
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Playback error: {e}")
            finally:
                if os.path.exists("temp_playback.mp3"):
                    try:
                        os.remove("temp_playback.mp3")
                    except:
                        pass
                self.playback_active = False
                self.speaking_active = False
                # Update GUI in main thread
                self.root.after(0, self.disable_stop_buttons)
                # Update status to ready if stopped by user
                if self.stop_playback_flag:
                    self.root.after(0, lambda: self.update_status("Ready for next recording"))
                self.audio_queue.task_done()
    
    def enable_stop_buttons(self):
        """Enable stop buttons when playback starts"""
        self.stop_speaking_btn.config(state=tk.NORMAL)
        
    def disable_stop_buttons(self):
        """Disable stop buttons when playback ends"""
        self.stop_speaking_btn.config(state=tk.DISABLED)
        
    def stop_speaking(self):
        """Stop the AI from speaking"""
        if self.speaking_active:
            self.stop_playback_flag = True
            # Clear the audio queue to prevent any remaining audio from playing
            try:
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        break
            except:
                pass
            self.update_status("Speech stopped by user - Ready for next recording")
        
    def update_status(self, message):
        """Update status bar"""
        self.status_var.set(message)
        self.root.update()
    
    def start_recording(self):
        """Start continuous recording"""
        if not self.recording_active:
            self.recording_active = True
            self.record_btn.config(state=tk.DISABLED)
            self.stop_record_btn.config(state=tk.NORMAL)
            self.update_status("Recording... Press Stop to finish")
            
            # Start recording in background thread
            threading.Thread(target=self.continuous_recording, daemon=True).start()
    
    def stop_recording(self):
        """Stop recording and process audio"""
        if self.recording_active:
            self.recording_active = False
            self.stop_record_btn.config(state=tk.DISABLED)
            self.update_status("Processing audio...")
    
    def continuous_recording(self):
        """Continuously record audio until stopped"""
        audio_chunks = []
        
        try:
            # Start recording
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32') as stream:
                while self.recording_active:
                    data, _ = stream.read(1024)  # Read in small chunks
                    audio_chunks.append(data)
                    
        except Exception as e:
            print(f"Recording error: {e}")
            self.root.after(0, lambda: self.update_status("Recording failed"))
            return
        
        # Combine all chunks
        if audio_chunks:
            self.recorded_audio = np.concatenate(audio_chunks, axis=0)
            # Process the recorded audio
            self.root.after(0, self.process_recorded_audio)
        else:
            self.root.after(0, lambda: self.update_status("No audio recorded"))
    
    def process_recorded_audio(self):
        """Process the recorded audio"""
        if self.recorded_audio is None:
            self.update_status("No audio to process")
            self.cleanup_recording()
            return
        
        # Start progress bar
        self.progress.start()
        
        # Run processing in separate thread
        threading.Thread(target=self.process_audio_pipeline, daemon=True).start()
    
    def process_audio_pipeline(self):
        """Full audio processing pipeline"""
        try:
            # 1. Transcribe
            self.root.after(0, lambda: self.update_status("Processing speech..."))
            text = self.transcribe_audio(self.recorded_audio, self.sample_rate)
            
            # Debugging: Print Whisper Transcription
            print(f"Whisper Transcription: {text}") 

            if not text or text.strip() == "":
                self.root.after(0, lambda: self.update_status("No speech detected"))
                return
                
            self.root.after(0, lambda: self.display_text(self.input_text, f"You: {text}"))
            
            # 2. Generate response
            self.root.after(0, lambda: self.update_status("Generating response..."))
            # The prompt is now simply the user's message as required by Cohere Chat API's 'message' parameter
            response = self.generate_response(text) 
            
            self.root.after(0, lambda: self.display_text(self.output_text, f"AI: {response}"))
            
            # 3. Speak response
            self.root.after(0, lambda: self.update_status("Speaking response..."))
            self.speak(response)
            
            self.root.after(0, lambda: self.update_status("Ready for next recording"))
            
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Error: {str(e)}"))
        finally:
            self.root.after(0, self.cleanup_recording)
    
    def cleanup_recording(self):
        """Clean up recording resources"""
        self.progress.stop()
        self.record_btn.config(state=tk.NORMAL)
        self.stop_record_btn.config(state=tk.DISABLED)
        self.recorded_audio = None
        self.recording_active = False
    
    def record_audio(self, duration=5, sample_rate=16000):
        """Record audio with fixed duration - kept for compatibility"""
        try:
            audio = sd.rec(int(duration * sample_rate),
                           samplerate=sample_rate,
                           channels=1,
                           dtype='float32')
            sd.wait()
            return audio, sample_rate
        except Exception as e:
            print(f"Recording error: {e}")
            return None, None
    
    def transcribe_audio(self, audio, sample_rate):
        """Convert speech to text with language support"""
        try:
            write("temp_recording.wav", sample_rate, audio)
            # Use selected language for transcription
            language = self.current_language if self.current_language in ["en", "ar"] else "en"
            result = self.model.transcribe("temp_recording.wav", language=language)
            return result["text"]
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
        finally:
            if os.path.exists("temp_recording.wav"):
                os.remove("temp_recording.wav")
    
    # Updated generate_response function using Cohere Chat API
    def generate_response(self, text):
        """Generate response using Cohere's Arabic model with Chat API"""
        try:
            # Debugging: Print current language and text being sent to Cohere
            print(f"Sending to Cohere (Language: {self.current_language}): {text}")
            
            # For the Chat API, the 'message' parameter is the user's input directly.
            # No need for complex prompts like with the Generate API if the model is designed for chat.
            response = self.co.chat(
                model="command-r7b-arabic-02-2025", # Specific Arabic model
                message=text, # The user's transcribed text
                max_tokens=200, # Increased slightly from 150 for more flexibility
                temperature=0.7, # Slightly higher temperature for more diverse responses if needed, adjust as you prefer
                # presence_penalty and frequency_penalty are not typically used with chat API,
                # as the model is designed to manage repetition in conversational context.
                # If needed, they are usually parameters for the 'generate' endpoint.
            )
            
            result_text = response.text.strip()
            
            # Debugging: Print Cohere Raw Response
            print(f"Cohere Raw Response: {result_text}")
            
            # Clean the Arabic response
            return self.clean_arabic_response(result_text)
            
        except Exception as e:
            print(f"حدث خطأ في توليد الرد: {e}")
            return "عذراً، حدث خطأ أثناء معالجة طلبك." # Arabic error message
    
    def clean_english_response(self, text):
        """Clean and format English response text"""
        if not text:
            return "I couldn't generate a proper response."
        
        # Remove any unwanted prefixes/suffixes
        text = text.strip()
        
        # Remove anything after two sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 2:
            text = ' '.join(sentences[:2])
        
        # Capitalize first letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
            
        return text
    
    def clean_arabic_response(self, text):
        """Clean and format Arabic response text - simplified for better results"""
        if not text:
            return "عذراً، لم أتمكن من إنشاء رد."
        
        # Simply strip leading/trailing whitespace and normalize internal spaces
        text = text.strip()
        # This replaces multiple spaces with a single space.
        # It also handles cases where Arabic words might be separated by non-standard whitespace.
        text = ' '.join(text.split()) 
        
        return text
    
    def starts_with_arabic(self, text):
        """Check if text starts with Arabic character"""
        if not text:
            return False
        return self.is_arabic_char(text[0])
    
    def is_arabic_char(self, char):
        """Check if character is Arabic"""
        arabic_range = (0x0600, 0x06FF)
        return arabic_range[0] <= ord(char) <= arabic_range[1]
    
    def speak(self, text):
        """Convert text to speech and queue for playback with language support"""
        try:
            # Use selected language for TTS
            # Debugging: Print text being sent to gTTS and its language
            print(f"gTTS text: '{text}' (Language: {self.current_language})")
            tts = gTTS(text=text, lang=self.current_language, slow=False)
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            self.audio_queue.put(audio_bytes)
        except Exception as e:
            print(f"Speech generation error: {e}")
    
    def display_text(self, widget, text):
        """Display text in GUI"""
        widget.config(state=tk.NORMAL)
        widget.insert(tk.END, text + "\n")
        widget.config(state=tk.DISABLED)
        widget.see(tk.END)
        self.root.update_idletasks()
    
    def cleanup(self):
        """Clean up resources"""
        self.progress.stop()
        self.record_btn.config(state=tk.NORMAL)
        self.stop_record_btn.config(state=tk.DISABLED)

    def on_close(self):
        """Clean up on window close"""
        self.audio_queue.put(None)  # Stop playback thread
        if hasattr(self, 'playback_process'):
            self.playback_process.terminate()
        self.root.destroy()

    def get_language_name(self):
        """Get display name for current language"""
        return "English" if self.current_language == "en" else "Arabic"
    
    def open_settings(self):
        """Open settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("700x900")
        settings_window.resizable(False, False)
        settings_window.grab_set()  # Make modal
        
        # Center the window
        window_width = 700
        window_height = 600
        screen_width = settings_window.winfo_screenwidth()
        screen_height = settings_window.winfo_screenheight()
        position_top = int(screen_height / 2 - window_height / 2)
        position_right = int(screen_width / 2 - window_width / 2)
        settings_window.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")
        
        main_frame = ttk.Frame(settings_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="⚙️ Settings", 
                                 font=('Segoe UI', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Language setting
        lang_frame = ttk.LabelFrame(main_frame, text="Language Settings", padding=15)
        lang_frame.pack(fill=tk.X, pady=(0, 15))
        
        lang_var = tk.StringVar(value=self.current_language)
        
        ttk.Label(lang_frame, text="Select Language:", font=('Segoe UI', 10)).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Radiobutton(lang_frame, text="🇺🇸 English", variable=lang_var, 
                        value="en").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(lang_frame, text="🇸🇦 Arabic", variable=lang_var, 
                        value="ar").pack(anchor=tk.W, pady=2)
        
        current_lang_label = ttk.Label(lang_frame, 
                                         text=f"Current: {self.get_language_name()}", 
                                         font=('Segoe UI', 9), 
                                         foreground='blue')
        current_lang_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Model setting
        model_frame = ttk.LabelFrame(main_frame, text="Whisper Model Settings", padding=15)
        model_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(model_frame, text="Select Model:", font=('Segoe UI', 10)).pack(anchor=tk.W, pady=(0, 5))
        
        model_var = tk.StringVar(value=self.current_model)
        model_combo = ttk.Combobox(model_frame, textvariable=model_var, 
                                     values=self.available_models, state="readonly", width=20)
        model_combo.pack(anchor=tk.W, pady=(0, 5))
        
        current_model_label = ttk.Label(model_frame, 
                                         text=f"Current: {self.current_model}", 
                                         font=('Segoe UI', 9), 
                                         foreground='blue')
        current_model_label.pack(anchor=tk.W, pady=(0, 5))
        
        model_info = ttk.Label(model_frame, 
                                 text="• tiny: fastest, least accurate\n• base: balanced performance\n• small: good balance\n• medium: recommended (default)\n• large: most accurate, slowest",
                                 font=('Segoe UI', 8),
                                 foreground='gray')
        model_info.pack(anchor=tk.W, pady=(5, 0))
        
        # Buttons frame with better layout
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Spacer to push buttons to the right
        spacer = ttk.Frame(btn_frame)
        spacer.pack(side=tk.LEFT, expand=True)
        
        apply_btn = ttk.Button(btn_frame, text="Apply", 
                                 command=lambda: self.apply_settings(settings_window, lang_var, model_var),
                                 style='Accent.TButton')
        apply_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", 
                                 command=settings_window.destroy)
        cancel_btn.pack(side=tk.RIGHT)
        
        settings_window.update_idletasks()
    
    def apply_settings(self, settings_window, lang_var, model_var):
        """Apply settings and close dialog"""
        old_language = self.current_language
        old_model = self.current_model
        
        # Get values from the variables
        self.current_language = lang_var.get()
        self.current_model = model_var.get()
        
        # Reload model if changed
        if old_model != self.current_model:
            self.update_status(f"Loading {self.current_model} model...")
            try:
                self.model = whisper.load_model(self.current_model)
                self.update_status("Model loaded successfully")
            except Exception as e:
                self.update_status(f"Error loading model: {str(e)}")
                # Revert to old model if loading fails
                self.current_model = old_model
        
        # Update UI labels if language changed
        if old_language != self.current_language:
            self.update_language_labels()
        
        settings_window.destroy()
        self.update_status(f"Settings applied - Language: {self.get_language_name()}, Model: {self.current_model}")
    
    def update_language_labels(self):
        """Update language labels in the UI"""
        # Update the frame labels to show current language
        self.input_frame.config(text=f" 🗣️ Your Speech ({self.get_language_name()}) ")
        self.output_frame.config(text=f" 🤖 AI Response ({self.get_language_name()}) ")
        self.update_status(f"Language changed to {self.get_language_name()}")
    
    def clear_chat(self):
        """Clear all text in chat areas"""
        self.input_text.config(state=tk.NORMAL)
        self.input_text.delete(1.0, tk.END)
        self.input_text.config(state=tk.DISABLED)
        
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        self.update_status("Chat cleared")
    
if __name__ == "__main__":
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
    except:
        print("Error: ffmpeg is required for audio playback")
        print("Install with: sudo apt install ffmpeg (Linux) or download from ffmpeg.org (Windows)")
        exit(1)
    
    root = tk.Tk()
    app = VoiceAssistant(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()