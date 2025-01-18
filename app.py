from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from google.cloud import storage
from openai import OpenAI
import subprocess

# Load environment variables
load_dotenv()


# Initialize Flask app
app = Flask(__name__)

# Configure OpenAI API Key
# openai.api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
#   organization='org-Tlp0CPXFKt1BP7VkhCITMuXN',
#   project='proj_yQ8mHxexgF89bgXx16bjfsKM',
    api_key =  os.getenv("OPENAI_API_KEY"),

)



# Initialize Google Cloud Storage client
storage_client = storage.Client()
BUCKET_NAME = os.getenv("BUCKET_NAME")  # Replace with your bucket name

# Configure your GCP bucket
PDF_FOLDER = "pdfs/"  # Folder inside the bucket to store PDFs
UPLOAD_FOLDER = "/tmp"  # Temporary folder for storing files

@app.route('/generate-resume', methods=['POST'])
def generate_resume():
    try:
        data = request.json
        job_description = data.get("job_description", "")
        latex_file_path = data.get("latex_file_path", "")

        if not job_description or not latex_file_path:
            return jsonify({"error": "Both job_description and latex_file_path fields are required"}), 400

    
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(latex_file_path)
        # print("blob==>",blob)
        
        if not blob.exists():
            return jsonify({"error": f"File {latex_file_path} not found in bucket {BUCKET_NAME}"}), 404

        latex_content = blob.download_as_text()
        
        prompt = f"""
        You are a LaTeX resume formatting expert. Given the following job description:
        
        {job_description}
        
        Read the provided LaTeX resume content and make the necessary modifications to tailor it to the job description. Specifically:
        1. Update the 'Technical Skills' section to include skills relevant to the job description as bullet points.
        2. Modify the 'Experience' section to highlight the most relevant experiences, ensuring they align with the job description.
        3. Add a 'Certifications' section if it's missing, or update it with certifications relevant to the job description.
        
        Existing LaTeX resume content:
        {latex_content}
        
        Return the updated LaTeX resume content, preserving the formatting and structure of the original LaTeX document.
        """

        response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert in resume updating."},
            {"role": "user", "content": prompt}
        ]
        )
        
        print(response);


        updated_latex = response.choices[0].message.content

        new_blob_name = f"{latex_file_path.split('.')[0]}_updated.tex"
        new_blob = bucket.blob(new_blob_name)
        new_blob.upload_from_string(updated_latex, content_type="text/plain")

        updated_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{new_blob_name}"

        return jsonify({
            "message": "Resume updated successfully",
            "updated_latex_url": updated_url
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload-resume', methods=['POST'])
def upload_file():
    # Check if the request has a file and name
    if 'file' not in request.files or 'name' not in request.form:
        return jsonify({"error": "Missing file or name"}), 400

    file = request.files['file']
    name = request.form['name']

    # Check if the file has the correct extension
    if not file.filename.endswith('.tex'):
        return jsonify({"error": "File must be a .tex file"}), 400

    # Create a unique object name in the bucket
    object_name = f"{name}/{file.filename}"

    # Upload the file to Google Cloud Storage
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(object_name)
    blob.upload_from_file(file, content_type=file.content_type)

    # Generate a public URL for the uploaded file (optional)
    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"

    return jsonify({"message": "File uploaded successfully", "url": public_url}), 200


@app.route('/convert_tex_to_pdf', methods=['POST'])
def convert_tex_to_pdf():
    try:
        tex_gcs_path = request.json.get("tex_file_path")
        if not tex_gcs_path:
            return jsonify({"error": "Missing .tex file path"}), 400

        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        tex_blob = bucket.blob(tex_gcs_path)
        if not tex_blob.exists():
            return jsonify({"error": "The .tex file does not exist in GCS"}), 404

        # Download the .tex file to a temporary location
        local_tex_path = os.path.join(UPLOAD_FOLDER, "temp.tex")
        tex_blob.download_to_filename(local_tex_path)

        # Set TEXINPUTS environment variable
        texinputs_path = "/usr/share/texlive/texmf-dist/tex/latex/preprint//:"
        env = os.environ.copy()
        env["TEXINPUTS"] = texinputs_path

        # Compile the LaTeX file to PDF
        compile_command = ["pdflatex", "-output-directory", UPLOAD_FOLDER, local_tex_path]
        subprocess.run(compile_command, check=True, env=env)

        # Get the PDF file path
        pdf_file_path = os.path.join(UPLOAD_FOLDER, "temp.pdf")
        if not os.path.exists(pdf_file_path):
            return jsonify({"error": "PDF generation failed"}), 500

        # Upload the PDF to GCS
        pdf_blob = bucket.blob("pdfs/temp.pdf")
        pdf_blob.upload_from_filename(pdf_file_path)

        # Generate a public URL for the PDF
        pdf_blob.make_public()
        pdf_url = pdf_blob.public_url

        # Cleanup temporary files
        os.remove(local_tex_path)
        os.remove(pdf_file_path)

        return jsonify({"message": "PDF generated successfully", "pdf_url": pdf_url}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "LaTeX compilation failed", "details": str(e)}), 500

    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080,debug=True)