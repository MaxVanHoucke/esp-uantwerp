"""@package
This package processes all routing requests.
"""

from flask_login import current_user
from flask import render_template, Blueprint, request, jsonify, session, current_app, \
    send_from_directory
from src.controllers.projects.manage_projects import manage
from src.models import TypeDataAccess, ProjectDataAccess, EmployeeDataAccess, ResearchGroupDataAccess, \
    AcademicYearDataAccess, GuideDataAccess, Like, Registration, RegistrationDataAccess, LikeDataAccess, \
    LinkDataAccess, ClickDataAccess
from src.models.db import get_db
import datetime
import os
import src.controllers.projects.tools
from src.controllers.projects.recommendations import get_projects_with_recommendations
from werkzeug.utils import secure_filename
from src.utils.mail import send_mail

bp = Blueprint('projects', __name__)


@bp.route('/projects', methods=["GET", "POST"])
def projects():
    """
    Handles the GET & POST request to '/projects'.
    GET: requests to render page
    POST: request to edit project with sent data
    :return: render projects page / Json containing authorisation error / manage(data) function call
    """
    if request.method == "GET":
        return render_template('projects.html')
    else:
        if not current_user.is_authenticated or (current_user.role != "admin" and current_user.role != "employee"):
            return jsonify(
                {'success': False, "message": "You are not authorized to edit the selected projects"}), 400, {

                       'ContentType': 'application/json'}
        data = request.json

        for project in data["projects"]:
            if current_user.role != "admin" and not employee_authorized_for_project(current_user.name, project):
                return jsonify(
                    {'success': False, "message": "You are not authorized to edit the selected projects"}), 400, {
                           'ContentType': 'application/json'}

        return manage(data)


@bp.route('/get-all-projects-data', methods=['GET'])
def get_all_projects_data():
    """
    Handles the GET request to '/get-all-projects-data'.
    :return: Json containing all project data with their recommendation index.
    """
    return jsonify(get_projects_with_recommendations())


@bp.route('/projects-page-additional', methods=['GET'])
def get_projects_page_additional_data():
    """
    Handles the GET request to '/projects-page-additional'.
    :return: Json containing active types, employees and groups.
    """
    connection = get_db()
    active_only = not session.get("archive")

    all_types = TypeDataAccess(connection).get_types(active_only)
    employees = EmployeeDataAccess(connection).get_employees(active_only)
    groups = ResearchGroupDataAccess(connection).get_group_names(active_only)

    result = {
        "types": [obj.type_name for obj in all_types],
        "employees": [obj.name for obj in employees],
        "groups": groups
    }
    return jsonify(result)


@bp.route('/project-editor', methods=['POST'])
def update_project():
    """
    Handles the POST request to '/project-editor'.
    :return: project_editor(data) function call
    """
    return src.controllers.projects.tools.project_editor(request.json)


@bp.route('/add-registration', methods=['POST'])
def add_registration():
    """
    Handles the POST request to '/project-editor'.
    :return: Json with success/failure status.
    """
    if current_user.is_authenticated and current_user.role == "student":
        try:
            project_id = request.form['data']
            registration = Registration(current_user.user_id, project_id, "Pending")
            RegistrationDataAccess(get_db()).add_registration(registration)

            project_title = ProjectDataAccess(get_db()).get_project(project_id, False).title

            msg = f"You registered for project {project_title}!\n" \
                f"You'll be notified when one of the supervisors changes your registration status.\n" \
                f"Best of luck!"

            send_mail(current_user.user_id + "@ad.ua.ac.be", "ESP Registration", msg)

            msg_employees = f"Student {current_user.name} ({current_user.user_id}) has registered for your project {project_title}.\n" \
                f"To change the registration status please visit the ESP site." \

            guides = GuideDataAccess(get_db()).get_guides_for_project(project_id)
            employee_access = EmployeeDataAccess(get_db())
            guides_with_info = [employee_access.get_employee(x.employee) for x in guides]

            for guide in guides_with_info:
                if guide.email:
                    send_mail(guide.email, "ESP Registration", msg_employees)

            return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
        except:
            return jsonify({'success': False, "message": "Failed to add a new registration!"}), 400, {
                'ContentType': 'application/json'}


@bp.route('/handle-registration', methods=['POST'])
def handle_registration():
    """
    Handles the POST request to '/handle-registration'.
    :return: Json with success/failure status. / redirects to login
    """
    if current_user.is_authenticated and current_user.role != "student":
        try:
            data = request.json

            RegistrationDataAccess(get_db()).update_registration(student_id=data['student_id'],
                                                                 project_id=data['project_id'],
                                                                 new_status=data['status'])

            project_title = ProjectDataAccess(get_db()).get_project(data['project_id'], False).title

            msg = f"Your registration for project {project_title} has changed to {data['status']}.\n" \
                f"For questions or remarks please contact the supervisors of the project."
            send_mail(data['student_id'] + "@ad.ua.ac.be", "ESP Registration Update", msg)
        except:
            return jsonify({'success': False, "message": "Failed to update registration!"}), 400, {
                'ContentType': 'application/json'}
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}

    else:
        return jsonify({'success': False, "message": "Failed to update registration!"}), 400, {
            'ContentType': 'application/json'}


@bp.route('/get-employee/<string:name>')
def get_employee_data(name):
    """
    Fetches all data of a certain employee.
    :param name: employee name
    :return: Json containing employee data
    """
    employee = EmployeeDataAccess(get_db()).get_employee_by_name(name)
    return jsonify(employee.to_dict())


@bp.route('/extend_project/<int:p_id>', methods=['POST'])
def extend_project(p_id):
    """
    Handles the POST request to '/extend_project/<int:p_id>'.
    Attempts to extend project with sent project id.
    :param p_id: project id
    :return: Json with success/failure status.
    """
    try:
        dao = ProjectDataAccess(get_db())
        dao.extend_project(p_id)
        try:
            dao.add_active_year(p_id, datetime.datetime.now().year + 1)
        except:
            pass
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except Exception as e:
        print(e)
        return jsonify({'success': False, "message": "Failed to extend project with id: " + str(p_id) + " !"}), 400, {
            'ContentType': 'application/json'}


@bp.route('/cancel_project_extension/<int:p_id>', methods=['POST'])
def cancel_project_extension(p_id):
    """
    Handles the POST request to '/extend_project/<int:p_id>'.
    Attempts to cancel project extension with sent project id.
    :param p_id: project id
    :return: Json with success/failure status.
    """
    try:
        ProjectDataAccess(get_db()).delete_project_extension(p_id)
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except:
        return jsonify({'success': False, "message": "Failed to cancel project extension with id: " + str(p_id) + " !"}) \
            , 400, {'ContentType': 'application/json'}


def employee_authorized_for_project(employee_name, project_id):
    """
    Checks if an employee has authorisation over a certain project.
    :param employee_name: employee name
    :param project_id: project id
    :return: Boolean
    """
    employee = EmployeeDataAccess(get_db()).get_employee_by_name(employee_name)
    guides = GuideDataAccess(get_db()).get_guides_for_project(project_id)
    for guide in guides:
        if guide.employee == employee.e_id:
            return True

    project = ProjectDataAccess(get_db()).get_project(project_id, False)
    return employee.research_group == project.research_group


@bp.route('/notify-extensions', methods=['GET', 'POST'])
def notify_extensions():
    """
    Handles the GET & POST request to '/notify-extensions'.
    Marks all projects for extension and adds the next academic year to the database.
    :return: Json with success/failure status.
    """
    try:
        project_access = ProjectDataAccess(get_db())
        academic_year_access = AcademicYearDataAccess(get_db())
        project_access.mark_all_projects_for_extension()
        try:
            academic_year_access.add_academic_year(datetime.datetime.now().year + 1)
        except:
            pass
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except Exception as e:
        return jsonify({'success': False, "message": "Failed to extend all projects!"}), 400, {
            'ContentType': 'application/json'}


@bp.route('/enforce-extensions', methods=['POST'])
def enforce_extensions():
    try:
        ProjectDataAccess(get_db()).enforce_extensions()
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except:
        return jsonify({'success': False, "message": "Failed to enforce extensions"}), 400, {
            'ContentType': 'application/json'}


@bp.route('/project-page')
def project_page():
    """
    Increases link strength upon a click.
    :return: render project page
    """
    if "from" in request.args and "project_id" in request.args:
        LinkDataAccess(get_db()).update_match_percent(request.args["from"], request.args["project_id"], 0.05)

    return render_template('project.html')


@bp.route('/can-modify/<p_id>')
def can_modify(p_id):
    """
    Checks if a project is modifiable.
    :param p_id: project id
    :return: Json with Boolean
    """
    modifiable = (current_user.is_authenticated and
                  (current_user.role == "admin" or
                   (current_user.role == "employee" and employee_authorized_for_project(current_user.name, p_id)))
                  )
    return jsonify({"modify": modifiable})


@bp.route('/like-project', methods=['POST'])
def like_project():
    """
    Handles the POST request to '/like-project'.
    Attempts to add a like for a certain project for the current user.
    :return: Json with success/failure status.
    """
    if not current_user.is_authenticated:
        return jsonify({'success': False}), 400, {'ContentType': 'application/json'}
    else:
        data = request.form['data']
        obj = Like(student_id=current_user.user_id, project=data)
        LikeDataAccess(get_db()).add_like(obj)
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}


@bp.route('/unlike-project', methods=['POST'])
def unlike_project():
    """
    Handles the POST request to '/unlike-project'.
    Attempts to remove a like for a certain project for the current user.
    :return: Json with success/failure status.
    """
    if not current_user.is_authenticated:
        return jsonify({'success': False}), 400, {'ContentType': 'application/json'}
    else:
        data = request.form['data']
        LikeDataAccess(get_db()).remove_like(current_user.user_id, data)
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}


@bp.route('/get-all-project-data/<int:p_id>', methods=['GET'])
def get_all_project_data(p_id):
    """
    Handles the GET request to '/get-all-project-data/<int:p_id>'.
    :param p_id: project id
    :return: Json with all project data, the research group and links.
    """
    active_only = not session["archive"]
    project_access = ProjectDataAccess(get_db())
    p_data = project_access.get_project(p_id, active_only)

    if current_user.is_authenticated and current_user.role == "student":
        p_data.liked = LikeDataAccess(get_db()).is_liked(p_data.project_id, current_user.user_id)

    # Add linked projects
    linked_projects = LinkDataAccess(get_db()).get_links_for_project(p_id)
    linked_projects_data = set()
    for link in linked_projects:
        if len(linked_projects_data) >= 4:
            break
        linked_projects_data.add(project_access.get_project(link.project_2, active_only))

    # Fill linked projects list with most viewed projects
    if len(linked_projects_data) < 4:
        projects_most_views = project_access.get_most_viewed_projects(8, active_only)
        i = 0
        while len(linked_projects_data) < 4:
            if not projects_most_views[i].project_id == p_id:
                linked_projects_data.add(projects_most_views[i])
            i += 1

    try:
        research_group = ResearchGroupDataAccess(get_db()).get_research_group(p_data.research_group).to_dict()
    except:
        research_group = None

    return jsonify({"project_data": p_data.to_dict(), "research_group": research_group,
                    "links": [obj.to_dict() for obj in linked_projects_data]})


@bp.route('/save-attachment', methods=['POST'])
def save_attachment():
    """
    Handles the POST request to '/save-attachment'.
    :return: Json with success/failure status, file name and file location.
    """
    if 'file' not in request.files:
        return jsonify({'success': False}), 400, {'ContentType': 'application/json'}

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False}), 400, {'ContentType': 'application/json'}

    filename = secure_filename(file.filename)
    upload_dir = os.path.join(current_app.config['file-storage'], 'attachments')

    if not os.path.isdir(upload_dir):
        os.mkdir(upload_dir)

    # Make sure no files get overwritten
    while filename in os.listdir(upload_dir):
        filename = "1" + filename

    file.save(os.path.join(upload_dir, filename))

    return jsonify({'success': True, 'name': file.filename, 'file_location': filename}), 200, {
        'ContentType': 'application/json'}


@bp.route('/get-attachment/<path:filename>')
def get_attachment(filename):
    """
    Fetches attachment from given filename.
    :param filename: file name
    :return: Json with success/failure status / attachment
    """
    if secure_filename(filename):
        return send_from_directory(os.path.join(current_app.config['file-storage'], 'attachments'), filename)
    return jsonify({'success': False}), 400, {'ContentType': 'application/json'}


@bp.route('/add-view/<int:p_id>', methods=['POST'])
def add_view(p_id):
    """
    Handles the POST request to '/add-view/<int:p_id>'.
    :param p_id: project id
    :return: Json with success/failure status
    """
    try:
        ProjectDataAccess(get_db()).add_view_count(p_id, 1)
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except:
        print("Failed to count a view for project " + str(p_id) + ".")
        return ""


@bp.route('/search/<search_query>', methods=['GET'])
def search(search_query):
    """
    Handles the GET request to '/search/<search_query>'.
    :param search_query: search query
    :return: Json with results
    """
    project_access = ProjectDataAccess(get_db())
    active_only = not session.get("archive")
    results = project_access.search(search_query, active_only)
    return jsonify(results)


@bp.route('/register-user-data/<int:p_id>', methods=['POST'])
def register_user_data(p_id):
    """
    Handles the POST request to '/register-user-data/<int:p_id>'.
    :param p_id: project id
    :return: Json with success/failure status
    """
    try:
        ProjectDataAccess(get_db()).add_view_count(p_id, 1)
        if session.get('session_id') is not None:
            ClickDataAccess(get_db()).add_project_click(p_id, session['session_id'])
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except:
        return jsonify(
            {'success': True, 'message': "Failed to register user behaviour for project " + str(p_id) + "."}), 400, {
                   'ContentType': 'application/json'}


@bp.route('/update-recommendations/<int:p1_id>/<int:p2_id>/<float:amount>', methods=['POST'])
def update_recommendations(p1_id, p2_id, amount):
    """
    Handles the POST request to '/update-recommendations/<int:p1_id>/<int:p2_id>/<float:amount>'.
    :param p1_id: project 1 id
    :param p2_id: project 2 id
    :param amount: percentage match amount
    :return: Json with success/failure status
    """
    try:
        LinkDataAccess(get_db()).update_match_percent(p1_id, p2_id, amount)
        return jsonify({'success': True}), 200, {'ContentType': 'application/json'}
    except:
        print("Failed to update recommendations for project " + str(p1_id) + " and project " + str(p2_id) + ".")
        return ""


@bp.route('/csv-data', methods=['GET'])
def get_csv_data():
    """
    Handles the GET request to '/csv-data', which retrieves data about all project registrations.
    :return: Json with success/failure status / data
    """
    if not current_user.is_authenticated or (current_user.role != "admin" and current_user.role != "employee"):
        return jsonify(
            {'success': False, "message": "You are not authorized to access this data"}), 400, {
                   'ContentType': 'application/json'}
    else:
        data = RegistrationDataAccess(get_db()).get_csv_data()
        return jsonify(data)