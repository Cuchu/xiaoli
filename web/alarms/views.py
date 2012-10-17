#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime

from sqlalchemy import desc, func 

from jinja2 import Markup

from flask import Blueprint, request, session, url_for, \
    redirect, render_template, g, flash

from tango import db

from jinja2 import Markup

from tango import user_profile

from tango.login import login_required, current_user

from tango.ui import menus, Menu

from tango.ui import tables

from tango.ui import Widget, add_widget

from tango.ui.tables import TableConfig

from tango.models import Query, Profile

from .models import Alarm, AlarmSeverity, History, AlarmClass, AlarmKnowledge

from .forms import QueryNewForm, AlarmAckForm, AlarmClearForm, AlarmClassForm, AlarmKnowledgeForm, AlarmFilterForm

from .tables import AlarmTable, QueryTable, HistoryTable, AlarmClassTable, AlarmKnowledgeTable

import constants

alarmview = Blueprint("alarms", __name__)

#===============================================================
#当前告警和历史告警 
#===============================================================
def alarm_filter(cls, query, form):
    """告警过滤"""
    alarm_class = form.alarm_class.data
    if alarm_class:
        query = query.filter(cls.alarm_class_id == alarm_class.id)
    start_date = form.start_date.data
    if start_date:
        query = query.filter(cls.first_occurrence >= start_date)
    end_date = form.end_date.data
    if end_date:
        query = query.filter(cls.first_occurrence <= end_date)
    keyword = form.keyword.data
    if keyword and keyword != '':
        query = query.filter(db.or_(
                    cls.alarm_alias.ilike('%'+keyword+'%'),
                    cls.node_alias.ilike('%'+keyword+'%')))
    return query

def alarm_severities():
    q = db.session.query(AlarmSeverity, func.count(Alarm.id).label('count'))
    q = q.outerjoin(Alarm, AlarmSeverity.id == Alarm.severity)
    q = q.group_by(AlarmSeverity).order_by(AlarmSeverity.id.desc())
    return q

@alarmview.route('/alarms', methods = ['GET'])
def index():
    filterForm = AlarmFilterForm(formdata=request.args)
    query = alarm_filter(Alarm, Alarm.query, filterForm)
    severity = request.args.get('severity')
    if severity:
        query = query.filter(Alarm.severity == AlarmSeverity.name2id(severity))
    severities = alarm_severities().all()
    total = sum([c for s, c in severities])
    table = AlarmTable(query)
    profile = user_profile(AlarmTable._meta.profile)
    TableConfig(request, profile).configure(table)
    return render_template("/alarms/index.html",
        table = table, filterForm = filterForm, 
        severities = severities, total = total)

@alarmview.route('/alarms/<int:id>')
def alarm_show(id):
    alarm = Alarm.query.get_or_404(id)
    return render_template("/alarms/detail.html", alarm=alarm)

@alarmview.route('/alarms/ack/<int:id>', methods=['GET', 'POST'])
def alarm_ack(id):
    form = AlarmAckForm()
    alarm = Alarm.query.get_or_404(id)
    if request.method == 'POST' and form.validate_on_submit():
        alarm.acked = 1
        alarm.alarm_state = 2
        alarm.acked_time = datetime.now()
        alarm.acked_user = current_user.username
        alarm.acked_note = form.acked_note.data
        db.session.commit()
        return redirect(url_for('.index'))
    else: # request.method == 'GET':
        form.process(obj=alarm)
        return render_template('/alarms/ack.html', alarm=alarm, form=form)

@alarmview.route('/alarms/clear/<int:id>', methods=['GET', 'POST'])
def alarm_clear(id=None):
    form = AlarmClearForm()
    alarm = Alarm.query.get_or_404(id)
    if request.method == 'POST' and form.validate_on_submit():
        alarm.cleared = 1
        alarm.severity = 0
        alarm.alarm_state = 3
        alarm.cleared_time = datetime.now()
        alarm.cleared_user = current_user.username
        alarm.cleared_note = form.cleared_note.data
        db.session.commit()
        return redirect(url_for('.index'))
    else:
        form.process(obj=alarm)
        return render_template('/alarms/clear.html', alarm=alarm, form=form)

@alarmview.route('/alarms/histories')
def histories():
    filterForm = AlarmFilterForm(formdata=request.args)
    query = alarm_filter(History, History.query, filterForm)
    table = HistoryTable(query)
    profile = user_profile(HistoryTable._meta.profile)
    TableConfig(request, profile).configure(table)
    return render_template("/alarms/histories.html",
        table=table, filterForm=filterForm)

@alarmview.route('/alarms/console')
def alarm_console():
    return render_template("/alarms/console.html")

@alarmview.route('/alarms/statistics/active')
@login_required
def statistics_active():
    return render_template('/alarms/statistics/active.html')
    
@alarmview.route('/alarms/statistics/history')
@login_required
def statistics_history():
    return render_template('/alarms/statistics/history.html')

#TODO:
@alarmview.route('/alarms/classes')
@login_required
def classes():
    keyword = request.args.get('keyword', '')
    query = AlarmClass.query
    if keyword:
        query = query.filter(db.or_(AlarmClass.name.ilike('%'+keyword+'%'),
                                    AlarmClass.alias.ilike('%'+keyword+'%')))
    table = AlarmClassTable(query)
    profile = user_profile(AlarmClassTable.profile)
    TableConfig(request, profile).configure(table)
    return render_template("/alarms/classes/index.html", table=table, keyword=keyword)

@alarmview.route('/alarms/classes/edit/<int:id>', methods=['GET', 'POST'])
def class_edit(id):
    form = AlarmClassForm()
    alarm_class = AlarmClass.query.get_or_404(id)
    if request.method == 'POST' and form.validate_on_submit():
        form.populate_obj(alarm_class)
        db.session.add(alarm_class)
        db.session.commit() 
        flash(u'告警类型修改成功')
        return redirect(url_for('alarms.classes'))
    form.process(obj=alarm_class)
    return render_template("/alarms/classes/edit.html", form = form, alarm_class = alarm_class)

@alarmview.route("/alarms/knowledges/")
@login_required
def knowledges():
    profile = user_profile(AlarmKnowledgeTable.profile)
    table = AlarmKnowledgeTable(AlarmKnowledge.query)
    TableConfig(request, profile).configure(table)
    return render_template('/alarms/knowledges/index.html', table=table)

@alarmview.route('/alarms/knowledges/new', methods=['GET', 'POST'])
@login_required
def knowledge_new():
    form = AlarmKnowledgeForm()
    if request.method == 'POST' and form.validate_on_submit():
        record = AlarmKnowledge()
        form.populate_obj(record)
        db.session.add(record)
        db.session.commit()
        flash("Add Alarm Knowledge Successfully!")
        return redirect(url_for('.knowledges'))
    return render_template('/alarms/knowledges/new.html', form=form)

@alarmview.route('/alarms/knowledges/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def knowledge_edit(id):
    form = AlarmKnowledgeForm()
    record = AlarmKnowledge.query.get_or_404(id)
    if request.method == 'POST' and form.validate_on_submit():
        form.populate_obj(record)
        db.session.add(record)
        db.session.commit()
        flash("Edit Alarm Knowledge Successfully!")
        return redirect(url_for('.knowledges'))
    form.process(obj=record)
    return render_template('/alarms/knowledges/edit.html', form=form, record=record)

@alarmview.route('/alarms/settings', methods=['GET', 'POST'])
def settings():
    q = Setting.query.filter_by(mod='alarms')
    t = SettingTable(q)
    return render_template('/alarms/settings.html', table=t)

@alarmview.app_template_filter("alarm_severity")
def alarm_severity_filter(s):
   return Markup('<span class="label severity-%s">%s</span>' % (s, constants.SEVERITIES[int(s)]))

@alarmview.app_template_filter("alarm_state")
def alarm_state_filter(s):
    return constants.STATES[int(s)] 

menus.append(Menu('alarms', u'故障', '/alarms'))

add_widget(Widget('event_summary', u'告警统计', url = '/widgets/alarm/summary'))
add_widget(Widget('event_statistics', u'告警概要', content='<div style="height:100px">......</div>'))
add_widget(Widget('dashboard1', 'Dashboard1', ''))
add_widget(Widget('dashboard2', 'Dashboard2', ''))

