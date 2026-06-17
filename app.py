import os
import shutil
import tempfile
from flask import Flask, request, render_template, send_file, jsonify
from fm_automation import FrameMakerAutomation
from mif_translator import MifTranslator

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'fm_file' not in request.files or 'docx_file' not in request.files:
        return jsonify({'error': 'Missing files. Please upload both FrameMaker (.fm) and Word (.docx) files.'}), 400
        
    fm_file = request.files['fm_file']
    docx_file = request.files['docx_file']
    
    if fm_file.filename == '' or docx_file.filename == '':
        return jsonify({'error': 'No files selected.'}), 400

    # Create a unique temporary directory for this request's processing
    temp_dir = tempfile.mkdtemp(dir=UPLOAD_FOLDER)
    
    fm_path = os.path.join(temp_dir, fm_file.filename)
    docx_path = os.path.join(temp_dir, docx_file.filename)
    
    fm_file.save(fm_path)
    docx_file.save(docx_path)
    
    # Define MIF paths in temp directory
    mif_name = os.path.splitext(fm_file.filename)[0] + ".mif"
    mif_path = os.path.join(temp_dir, mif_name)
    
    trans_mif_name = os.path.splitext(fm_file.filename)[0] + "_translated.mif"
    trans_mif_path = os.path.join(temp_dir, trans_mif_name)
    
    trans_fm_name = os.path.splitext(fm_file.filename)[0] + "_translated.fm"
    trans_fm_path = os.path.join(temp_dir, trans_fm_name)

    try:
        automation = FrameMakerAutomation()
        
        # Step 1: Export FM to MIF
        print(f"Exporting FM to MIF: {fm_path} -> {mif_path}")
        success = automation.run_job("EXPORT", fm_path, mif_path, timeout=180)
        if not success:
            return jsonify({'error': 'Failed to convert FrameMaker file to MIF. Make sure Adobe FrameMaker is installed and not blocked.'}), 500
            
        # Step 2: Translate MIF using Docx
        print(f"Translating MIF: {mif_path} using {docx_path}")
        translator = MifTranslator(docx_path)
        translator.translate_file(mif_path, trans_mif_path)
        
        # Step 3: Import Translated MIF to FM
        print(f"Importing MIF to FM: {trans_mif_path} -> {trans_fm_path}")
        success = automation.run_job("IMPORT", trans_mif_path, trans_fm_path, timeout=180)
        if not success:
            return jsonify({'error': 'Failed to convert translated MIF back to FrameMaker format.'}), 500
            
        # Save output path in a safe location outside temp dir so we can clean up temp dir before sending
        final_download_path = os.path.join(UPLOAD_FOLDER, trans_fm_name)
        shutil.copy(trans_fm_path, final_download_path)
        
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return jsonify({
            'success': True,
            'download_url': f'/download/{trans_fm_name}'
        })
        
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found.", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
