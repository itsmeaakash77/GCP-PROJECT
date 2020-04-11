import logging
import os
from flask import Flask, redirect, render_template, request
from google.cloud import datastore
from google.cloud import storage
from google.cloud import vision
from google.cloud import texttospeech

CLOUD_STORAGE_BUCKET = os.environ.get('CLOUD_STORAGE_BUCKET')


app = Flask(__name__)


@app.route('/')
def homepage():
    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()

    # Use the Cloud Datastore client to fetch information from Datastore about
    # each photo.
    query = datastore_client.query(kind='Faces')
    
    # getting the image_entities by fetching
    image_entities = list(query.fetch())

    # Return a Jinja2 HTML template and pass in image_entities as a parameter.
    return render_template('homepage.html', image_entities=image_entities)


@app.route('/upload_photo', methods=['GET', 'POST'])
def upload_photo():
    # getting the image file as photo
    photo = request.files['file']

    # Creating a Cloud Storage client.
    storage_client = storage.Client()

    # Getting the bucket where the file is uploaded to.
    bucket = storage_client.get_bucket(CLOUD_STORAGE_BUCKET)

    # Create a new blob and upload the file's content.
    blob1 = bucket.blob(photo.filename)
    blob1.upload_from_string(photo.read(), content_type=photo.content_type)

    # Make the blob publicly viewable.
    blob1.make_public()

    # Create a Cloud Vision client.
    vision_client = vision.ImageAnnotatorClient()

    # Use the Cloud Vision client to detect a face for our image.
    # representing the image url as a string
    image_url = 'gs://{}/{}'.format(CLOUD_STORAGE_BUCKET, blob1.name)
    # passing the image source to vision api
    image = vision.types.Image(source=vision.types.ImageSource(gcs_image_uri=image_url))
    # getting the response and assigning a variable
    response=vision_client.document_text_detection(image=image)
    # convert the response as a text-document
    docu = response.full_text_annotation.text
    
    # Creating the TexttoSpeech clienct
    text_client= texttospeech.TextToSpeechClient()
    # synthesis the input text
    synthesis_text= texttospeech.types.SynthesisInput(text=docu)
    # converting the text to speech with language as en-US and voice to NEUTRAl
    voice = texttospeech.types.VoiceSelectionParams(language_code='en-US',ssml_gender=texttospeech.enums.SsmlVoiceGender.NEUTRAL)
    # configuring the audio as a MP3
    audio_config=texttospeech.types.AudioConfig(audio_encoding=texttospeech.enums.AudioEncoding.MP3)
    # finally converting the text to speech and getting the response using texttospeech client
    audio_response=text_client.synthesize_speech(synthesis_text,voice,audio_config)
    
    # Creating a blob for the output audio file
    blob2=bucket.blob('output.mp3')
    # Converting the audio response as a 'output.mp3'
    with open('output.mp3','wb') as output:
       output.write(audio_response.audio_content)
       print('content written')
    # Now converting the output file into the blob2
    with open('output.mp3','rb') as output:
        blob2.upload_from_file(output)
    #Now making the blob2 public to access the data publicly
    blob2.make_public() 
    
    #getting the voice url
    voice_url='https://storage.googleapis.com/{}/{}'.format(CLOUD_STORAGE_BUCKET,blob2.name)
    
    
    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()
   
    kind = 'Faces'
    key = datastore_client.key(kind, blob1.name)
    
    entity = datastore.Entity(key)
    entity['blob_name'] = blob1.name
    entity['image_public_url'] = blob1.public_url
    entity['timestamp'] = voice_url
    entity['joy'] = docu
    
    #putting the entity using put command
    datastore_client.put(entity)
    # once work is done it is redirecting
    return redirect('/')


@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


if __name__ == '__main__':
       app.run(host='127.0.0.1', port=8080, debug=True)    
